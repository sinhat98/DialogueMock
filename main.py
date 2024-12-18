from dotenv import load_dotenv

load_dotenv()


import os
import json
import base64
import threading
from typing import Any
from fastapi import FastAPI, WebSocket, Request, Form, status
from fastapi.responses import Response
from starlette.websockets import WebSocketState
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse
from twilio.rest.api.v2010.account.call import CallInstance
from twilio.base import exceptions as twilio_exceptions

from src.modules.dialogue.utils.template import tts_label2text
from src.modules.dialogue.utils.constants import TTSLabel
from src.bridge import ASRBridge, TTSBridge, LLMBridge
from src.bridge.dialog_bridge_with_ic import DialogBridgeWithIntentClassification


from src.utils.twilio_account import TwilioAccount
from src.utils import gcs as gcs_service

import logging
import http
from pathlib import Path

from dotenv import load_dotenv
import hashlib

import pandas as pd


load_dotenv()

from src.utils import get_custom_logger
from src.utils.firestore import FirestoreClient
from src.utils.conversation_log import ConversationLogger

logger = get_custom_logger(__name__)


for logger_name in logging.Logger.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.INFO)

templates_dir = Path(__file__).parent / "templates"
templates_wav_dir = templates_dir / "wav"

app = FastAPI()
APP_URL = os.environ["APP_URL"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ENV = os.getenv("ENV")
TENANT_ID = os.getenv("TENANT_ID")
PROJECT_ID = os.getenv("PROJECT_ID")
USE_INITIAL_ROUTING = os.getenv("USE_INITIAL_ROUTING", "false").lower() == "true"
DEFAULT_DIALOG_PATTERN = int(os.getenv("DEFAULT_DIALOG_PATTERN", "1"))

async def get_from_phone_number(client: Client, call_sid: str) -> str:
    call = client.calls(call_sid).fetch()
    return call._from


async def get_to_phone_number(client: Client, call_sid: str) -> str:
    call = client.calls(call_sid).fetch()
    return call.to



@app.post("/twiml")
async def twiml():
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=f"wss://{APP_URL}/ws")
    # response.say("お電話ありがとうございます。SHIFT渋谷店でございます。お電話のご用件をお話しください。", voice="alice", language="ja-JP")

    connect.append(stream)
    response.append(connect)
    logger.info(response)

    return Response(
        content=str(response),
        status_code=200,
        headers={"Content-Type": "text/html"},
    )


async def init_conversation_events(firestore_client, call_sid, customer_phone_number):
    conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()
    env = ENV
    tenant_id = TENANT_ID
    project_id = PROJECT_ID
    customer_id = hashlib.sha1(customer_phone_number.encode()).hexdigest()

    customer_data = {
        "developer": False,
        "disabled": False,
        "display_name": "",
        "note": "",
        "preview": False,
        "voice": {"customer_phone_number": customer_phone_number, "note": ""},
        "updated_at": firestore_client.get_timestamp(),
    }
    tenant_ref = firestore_client.get_tenant_ref(env, tenant_id)
    logger.info("Tenant ref: %s", tenant_ref.path)

    customer_ref = firestore_client.create_customer(
        tenant_ref, customer_id, customer_data
    )
    logger.info("Customer ref: %s", customer_ref.path)

    # プロジェクトの参照を取得
    project_ref = firestore_client.get_project_ref(customer_ref, project_id)
    logger.info("Project ref: %s", project_ref.path)

    # 対話データを作成
    CALLING = "自動応答中"
    DIRECTION = "inbound"

    conversation_data = {
        "entity": {},
        "intent": {"welcome": "START_CONVERSATION"},
        "is_active": False,
        "status": CALLING,
        "direction": DIRECTION,
        "ivr_count": 0,
        "created_at": firestore_client.get_timestamp(),
        "conversation_status": "left",
        "for_query": {
            "env": env,
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "project_id": project_id,
            "customer_phone_number": customer_phone_number,
            "conversation_id": conversation_id,
        },
        "reading_form": {},
    }
    firestore_client.set_conversation_ref(project_ref, conversation_id)
    firestore_client.create_conversation(conversation_data)
    logger.info("Conversation ref: %s", firestore_client.conversation_ref.path)

    return firestore_client


def get_gcs_path_from_params(subdomain: str, project_id: str, customer_phone_number: str, call_sid: str) -> str:
    """
    URLパラメータからGCSパスを構築する
    
    Args:
        subdomain: テナントのサブドメイン
        project_id: プロジェクトID
        customer_phone_number: 顧客の電話番号
        call_sid: 通話ID

    Returns:
        str: GCSパス
    """
    # 電話番号からcustomer_idを生成
    customer_id = hashlib.sha1(f"+{customer_phone_number}".encode()).hexdigest()
    # call_sidからconversation_idを生成
    conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()
    
    # GCSパスを構築
    gcs_path = f"{subdomain}/{project_id}/{customer_id}/{conversation_id}"
    return gcs_path


@app.post("/recording/twilio2gcs")
async def post_twilio2gcs(
    request: Request,
    RecordingUrl: str = Form(...),
    RecordingSid: str = Form(...),
    AccountSid: str = Form(...),
    CallSid: str = Form(...),
) -> Response:
    recording_url = RecordingUrl
    recording_sid = RecordingSid
    account_sid = AccountSid
    call_sid = CallSid
    account_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")

    twilio_account = TwilioAccount(account_sid, account_auth_token)
    project_id = str(request.query_params.get("project_id"))
    customer_phone_number = str(request.query_params.get("customer_phone_number"))
    customer_phone_number = "+" + customer_phone_number
    customer_id = hashlib.sha1(customer_phone_number.encode()).hexdigest()
    conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()
    subdomain = os.environ.get("TENANT_SUBDOMAIN")
    gcs_path = f"{subdomain}/{project_id}/{customer_id}/{conversation_id}/audio"
    await gcs_service.twilio2gcs(
        recording_url,
        gcs_path,
        account_sid,
        custom_value=recording_sid,
    )
    logger.info(f"finish to copy wav file to gcs. path={gcs_path}")

    delete_twilio_call_recording(twilio_account, recording_sid)

    return Response(
        headers={"Content-Type": "application/json"},
        content=json.dumps(
            {
                "recording_url": recording_url,
                "recording_sid": recording_sid,
            }
        ),
        status_code=status.HTTP_200_OK,
    )


def delete_twilio_call_recording(
    twilio_account: TwilioAccount, recording_sid: str
) -> Any:
    try:
        client = Client(twilio_account.account_sid, twilio_account.auth_token)
        call = client.recordings(recording_sid).delete()
        logger.info(f"finish to delete twilio recording file. sid={recording_sid}")
        return call
    except Exception as e:
        logger.error(f"Error in delete twilio recording file. {e}", stack_info=True)
        return None


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    logger.info("WS connection opened")

    await ws.accept()

    # init streaming client
    # data["event"] == "connected"
    data = await ws.receive_json()
    logger.info(f"Media WS: Received event '{data['event']}': {data}")

    # data["event"] == "start"
    data = await ws.receive_json()
    logger.info(f"Media WS: Received event '{data['event']}': {data}")

    asr_bridge = ASRBridge()
    tts_bridge = TTSBridge()

    t_tts = threading.Thread(target=tts_bridge.response_loop)

    t_tts.start()

    import asyncio

    def start_async_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    # 新しいイベントループを作成し、それを別のスレッドで実行
    new_loop = asyncio.new_event_loop()
    t_loop = threading.Thread(target=start_async_loop, args=(new_loop,))
    t_loop.start()

    stream_sid = data["start"]["streamSid"]
    call_sid = data["start"]["callSid"]
    account_sid = data["start"]["accountSid"]
    logger.info(
        f"stream_sid: {stream_sid}, call_sid: {call_sid}, account_sid: {account_sid}"
    )
    twilio_account = TwilioAccount(account_sid, os.environ.get("TWILIO_AUTH_TOKEN"))
    auth_token = twilio_account.auth_token
    custom_client = TwilioHttpClient(max_retries=3)
    client = Client(account_sid, auth_token, http_client=custom_client)
    aim_phone_number = await get_to_phone_number(client, call_sid)
    customer_phone_number = await get_from_phone_number(client, call_sid)
    logger.info(
        f"aim_phone_number: {aim_phone_number}, customer_phone_number: {customer_phone_number}"
    )
    
    conversation_logger = ConversationLogger(call_sid)
    logger.info(f"Conversation logger created {conversation_logger}")
    gcs_conversation_log_path = get_gcs_path_from_params(
        subdomain=os.environ.get("TENANT_SUBDOMAIN"),
        project_id=PROJECT_ID,
        customer_phone_number=customer_phone_number.replace('+', ''),
        call_sid=call_sid
    ) + "/conversation_log"


    recording_callback_url = f"https://{APP_URL}/recording/twilio2gcs?project_id={PROJECT_ID}&tenant_id={TENANT_ID}&customer_phone_number={customer_phone_number.replace('+', '')}#rc=2&rp=all"
    # client.calls(call_sid).recordings.create(
    #     recording_status_callback=recording_callback_url,
    #     recording_status_callback_method="POST",
    #     recording_channels="dual",
    # )

    firestore_client = FirestoreClient()
    firestore_client = await init_conversation_events(
        firestore_client, call_sid, customer_phone_number
    )

    tts_bridge.set_connect_info(stream_sid)
    logger.info("Set connect info")

    dialog_bridge = DialogBridgeWithIntentClassification()
    dialog_bridge.set_stream_sid(stream_sid)

    #####################################
    
    tts_bridge.add_response(dialog_bridge.get_initial_message())

    await dialog_bridge.send_tts(ws, tts_bridge, firestore_client, conversation_logger)
    threading.Thread(target=asr_bridge.start).start()

    is_finished = False
    while ws.application_state == WebSocketState.CONNECTED:
        data = await ws.receive_json()

        if data["event"] == "stop":
            logger.info(f"Media WS: Received event 'stop': {data}")
            break

        elif data["event"] == "media":
            media = data["media"]
            chunk = base64.b64decode(media["payload"])
            asr_bridge.add_request(chunk)
            dialog_bridge.vad_step(chunk)
            out = await dialog_bridge(
                ws,
                asr_bridge,
                tts_bridge,
                firestore_client=firestore_client,
                conversation_logger=conversation_logger,
            )

            if out["asr_done"]:
                logger.info("ASR done")
                asr_bridge.terminate()
                asr_bridge = ASRBridge()
                threading.Thread(target=asr_bridge.start).start()
                logger.info("Restarted asr bridge")

            # if out["bot_speak"]:
            #     asr_bridge.set_bot_speak(True)

        elif data["event"] == "mark" and data["mark"]["name"] == "continue":
            logger.info(f"Media WS: Received event 'mark': {data}")
            logger.info("Bot: Speaking is done")
            asr_bridge.reset()
            dialog_bridge.bot_speak = False
            # 暗黙確認時にのみバージインを許可するため、botが話し終わったタイミングでバージインを毎回オフにする
            dialog_bridge.allow_barge_in = False
            logger.info("set allow_barge_in to False")
            if is_finished or (dialog_bridge.dialogue_system.is_complete() and tts_bridge.is_empty):
                break
        elif data["event"] == "mark" and data["mark"]["name"] == "finish":
            is_finished = True
        else:
            raise "Media WS: Received unknown event"

    logger.info("Media WS: Connection closed")
    asr_bridge.terminate()
    # t_tts.join()

    logger.info("WS connection completedly closed")
    # disconnect twilio call
    try:
        client.calls(call_sid).update(
            twiml=twiml,
            status=CallInstance.UpdateStatus.COMPLETED,
        )
        await conversation_logger.save_conversation_log_to_gcs(gcs_conversation_log_path)
        conversation_logger.to_csv(f"{gcs_conversation_log_path.replace('/', '_')}.csv")
        
    except twilio_exceptions.TwilioRestException as e:
        logger.warning(f"Could not update CallContext because '{e}'")
    except http.client.RemoteDisconnected as e:
        logger.warning(f"Updating CallContext is RemoteDisconnected. Error is '{e}'")
        try:
            client.calls(call_sid).update(
                twiml=twiml, status=CallInstance.UpdateStatus.COMPLETED
            )
            await conversation_logger.save_conversation_log_to_gcs(gcs_conversation_log_path)
        except http.client.RemoteDisconnected as e:
            logger.error(
                f"Updating CallContext is twice RemoteDisconnected. Error is '{e}'"
            )
            raise e
