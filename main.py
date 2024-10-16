from dotenv import load_dotenv

load_dotenv()

import os
import base64
import threading
from fastapi import FastAPI, WebSocket
from fastapi.responses import Response
from starlette.websockets import WebSocketState
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse


from src.bridge import DialogBridge, ASRBridge, TTSBridge, LLMBridge
from src.bridge.dialog_bridge_v2 import DialogBridge as DialogBridgeV2
from src.bridge.dialog_bridge_v3 import DialogBridge as DialogBridgeV3
from src.utils.twilio_account import get_twilio_account

import logging
from pathlib import Path

from dotenv import load_dotenv
import hashlib


load_dotenv()

from src.utils import get_custom_logger
from src.utils.firestore import FirestoreClient
logger = get_custom_logger(__name__)


for logger_name in logging.Logger.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.INFO)

templates_dir = Path(__file__).parent / "templates"
templates_wav_dir = templates_dir / "wav"

app = FastAPI()
NGROK = os.environ["NGROK"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ENV = os.getenv("ENV")
TENANT_ID = os.getenv("TENANT_ID")
PROJECT_ID = os.getenv("PROJECT_ID")
CUSTOMER_PHONE_NUMBER = os.getenv("CUSTOMER_PHONE_NUMBER")


@app.post("/twiml")
async def twiml():
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=f"wss://{NGROK}/ws")
    # response.say("お電話ありがとうございます。SHIFT渋谷店でございます。お電話のご用件をお話しください。", voice="alice", language="ja-JP")

    connect.append(stream)
    response.append(connect)
    logger.info(response)

    return Response(
        content=str(response),
        status_code=200,
        headers={"Content-Type": "text/html"},
    )

def init_conversation_events(firestore_client, call_sid):
    conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()
    env = ENV
    tenant_id = TENANT_ID
    customer_phone_number = CUSTOMER_PHONE_NUMBER
    customer_id = hashlib.sha1(customer_phone_number.encode()).hexdigest()
    project_id = PROJECT_ID
    
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
    logger.info(f"Tenant ref: {tenant_ref.path}")
    
    
    customer_ref = firestore_client.create_customer(tenant_ref, customer_id, customer_data)
    logger.info(f"Customer ref: {customer_ref.path}")
    
    # プロジェクトの参照を取得
    project_ref = firestore_client.get_project_ref(customer_ref, project_id)
    logger.info(f"Project ref: {project_ref.path}")
    
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
    logger.info(f"Conversation ref: {firestore_client.conversation_ref.path}")

    return firestore_client


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
    llm_bridge = LLMBridge()
    # dialog_bridge = DialogBridge()
    # dialog_bridge = DialogBridgeV2()
    dialog_bridge = DialogBridgeV3()
    
    t_tts = threading.Thread(target=tts_bridge.response_loop)
    t_llm = threading.Thread(target=llm_bridge.response_loop)
    
    t_tts.start()
    t_llm.start()
    
    # llm_bridge.add_request("サンプル")
    # response = llm_bridge.get_response()
    
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
    twilio_account = await get_twilio_account(account_sid)
    auth_token = twilio_account.auth_token
    custom_client = TwilioHttpClient(max_retries=3)
    client = Client(account_sid, auth_token, http_client=custom_client)
    
    firestore_client = FirestoreClient()
    firestore_client = init_conversation_events(firestore_client, call_sid)
    
    dialog_bridge.set_stream_sid(stream_sid)
    tts_bridge.set_connect_info(stream_sid)
    tts_bridge.add_response("INITIAL")
    first = [
        0,
        "お電話ありがとうございます。新規ご予約を承ります。"
    ]
    logger.info(f"Bot: {first[1]}")
    
    initial_event_data = {
        "message": first[1],
        "sender_type": "bot",
        "entity": {},
        "is_ivr": False,
        "created_at": firestore_client.get_timestamp(),
    }
    event_id = firestore_client.add_conversation_event(initial_event_data)
    logger.info(f"[firestore] Added initial event: {event_id}")
    
    _, out = tts_bridge.audio_queue.get()
    await ws.send_text(out)
    threading.Thread(target=asr_bridge.start).start()
    
    
    recording_callback_url = f"https://{NGROK}/recording/twilio2gcs?project_id={PROJECT_ID}&tenant_id={TENANT_ID}&customer_phone_number={CUSTOMER_PHONE_NUMBER.replace('+', '')}#rc=2&rp=all"
    client.calls(call_sid).recordings.create(
        recording_status_callback=recording_callback_url,
        recording_status_callback_method="POST",
        recording_channels="dual",
    )
    

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
                llm_bridge,
                tts_bridge, 
                firestore_client=firestore_client,
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
            # asr_bridge.reset()
            dialog_bridge.bot_speak = False
            # 暗黙確認時にのみバージインを許可するため、botが話し終わったタイミングでバージインを毎回オフにする
            dialog_bridge.allow_barge_in = False 
            logger.info("set allow_barge_in to False")
            # asr_bridge.set_bot_speak(False)
            # dialog_bridge.bot_speak = False
            # asr_bridge.terminate()
            # asr_bridge = ASRBridge()
            # threading.Thread(target=asr_bridge.start).start()
        elif data["event"] == "mark" and data["mark"]["name"] == "finish":
            logger.info(f"Media WS: Received event 'finish': {data}")
            break
        else:
            raise "Media WS: Received unknown event"
        
        

    logger.info("Media WS: Connection closed")
    asr_bridge.terminate()
    # t_tts.join()

    logger.info("WS connection completedly closed")