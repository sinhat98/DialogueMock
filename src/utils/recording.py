import base64
import hashlib
import io
import json
import os
import wave
from datetime import datetime
from typing import Any, List, Tuple
from zoneinfo import ZoneInfo

import aiohttp
import numpy as np
from fastapi import APIRouter, Form, Request, Response, status
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

from src.utils import gcs as gcs_service
from src.utils.firestore import FirestoreClient
from src.utils.gcp import Call, ConversationStatus, PubSub as pubsub_driver
from src.utils.twilio_account import TwilioAccount, get_twilio_account
from src.utils.call_end_operation import list_by_project_id
from src.utils.call_status import CallStatus as CS
from src.utils.db import csqld
from src.utils.project import get_project
from src.utils.tenant import get_tenant

from src.utils import get_custom_logger


stt_reading_form_url: str = os.environ["STT_READING_FORM_URL"]
cooperation_app_url: str = os.environ["COOPERATION_APP_URL"]
env = os.environ["ENV"]
logger = get_custom_logger(__name__)

router = APIRouter()
reading_form_suffix = "_pn"
custom_client = TwilioHttpClient(max_retries=2)
firestore_client = FirestoreClient().client

@router.post("/twilio2gcs", tags=["/recording"])
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
    twilio_account = await get_twilio_account(account_sid)
    tenant_id = str(request.query_params.get("tenant_id"))
    project_id = str(request.query_params.get("project_id"))
    customer_phone_number = str(
        request.query_params.get("customer_phone_number")
    )

    customer_phone_number_or_sipuri = await get_customer_phone_number(
        account_sid,
        call_sid,
    )
    ## inboundの場合はfrom, outboundの場合はtoの値にてcustomer_idを生成する(streaming.py参照)
    ## SIP接続の場合も同様だが、outboundケースでのSIP接続利用は現状想定していないため、fromの値を利用する
    ## SIP接続の場合、エンドユーザ電話番号が連携元システムから取得できない可能性があるため、twilio APIから取得されるSIP URIにて生成する
    customer_id = hashlib.sha1(
        customer_phone_number_or_sipuri.encode()
    ).hexdigest()

    # 公衆回線の場合は、customer_phone_numberが空文字列になるため、customer_phone_number_or_sipuriを代入する
    # SIPの場合はcusomter_phone_numberに電話番号が代入される
    if customer_phone_number == "":
        customer_phone_number = customer_phone_number_or_sipuri
    else:
        customer_phone_number = "+" + customer_phone_number
    # 転送前切断かどうかを確認し、転送前切断であればログの後処理をするメソッド
    conversation_ref = await set_fs_is_active_false(
        project_id,
        customer_phone_number,
        customer_id,
        call_sid,
        account_sid,
    )

    conv_dic = conversation_ref.get().to_dict()
    try:
        fs_status = conv_dic["status"]
        ## tenantDBから設定を取得
        call_operations = await list_by_project_id(tenant_id, project_id)
        ## 設定がなければスキップ
        if len(call_operations) <= 0:
            pass

        ## 取得した情報を詰めて通知処理を実行
        for call_operation in call_operations:
            intentmap: dict[str, Any] = conv_dic["intent"]
            if (
                is_target_call(
                    call_operation.target_intent,
                    call_operation.exclude_intent,
                    intentmap,
                )
                is False
            ):
                ## 対象外callの場合はスキップ
                logger.info(
                    f"skip callend operation({call_operation.exec_function_name}): tenant_id={tenant_id}, project_id={project_id}, call_sid={call_sid}, conversation_id={hashlib.sha1(call_sid.encode()).hexdigest()}"
                )
                continue
            call = get_twilio_call_resource(twilio_account, call_sid)
            conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()
            _, aim_phone_number_or_sipuri = await get_aim_phone_number(
                account_sid, call_sid
            )
            aim_phone_number = aim_phone_number_or_sipuri
            if is_sip_call(aim_phone_number_or_sipuri):
                refs = await get_firestore_references(
                    project_id,
                    customer_id,
                    conversation_id,
                )
                ## sip接続の場合は、aim_phone_numberにSIP URIが設定されているため、AIMessenger電話番号をfirestoreから取得して設定し直す
                aim_phone_number = refs["project_ref"].to_dict()[
                    "aim_phone_number"
                ]

            is_transfer_failed: bool = fs_status == CS.CUTOFF_BEFORE_TRANSFER
            if is_transfer_failed == False:
                child_calls = get_twilio_child_call_resources(
                    twilio_account, call_sid
                )
                ## child_callsが転送由来とは限らないが、IVRなど転送に近しいものが取得されてくるはず
                ## これらは基本的に正常終了しているはずで、そうでない場合は何らかの操作が失敗しているとみなす
                for child_call in child_calls:
                    if child_call.status != "completed":
                        is_transfer_failed = True
                        logger.info(
                            f"finish to call cooperation-app function. childcall is not completed. CallSID={call_sid}, ChildCallSID={child_call.sid}, status={child_call.status}"
                        )
                        break

            call_start_time: datetime = call.start_time
            call_end_time: datetime = call.end_time
            params: dict[str, Any] = {
                "call_sid": call_sid,
                "conversation_id": conversation_id,
                "exec_function_name": call_operation.exec_function_name,
                "customer_phone_number": customer_phone_number,
                "aim_phone_number": aim_phone_number,
                "call_start_time": call_start_time.astimezone(
                    ZoneInfo("Asia/Tokyo")
                ).strftime("%Y-%m-%dT%H:%M:%S%z"),
                "call_end_time": call_end_time.astimezone(
                    ZoneInfo("Asia/Tokyo")
                ).strftime("%Y-%m-%dT%H:%M:%S%z"),
                "firestore_conversation_status": fs_status,
                "twilio_call_status": call.status,
                "is_transfer_failed": is_transfer_failed,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "target_intent": call_operation.target_intent,
            }
            logger.info(f"start callend operation: params={params}")
            request_url = f"{cooperation_app_url}/callend/operation"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=request_url,
                    json=params,
                ) as resp:
                    result = await resp.json(content_type=None)
                    logger.info(
                        f"finish to call cooperation-app function. params={params}, result={result}"
                    )

            ## TODO: いずれPubSubに移行する

    except Exception as e:
        ## 各通知処理に失敗しても、処理は継続する
        logger.error(f"Error in notification process. {e}", stack_info=True)

    # conversationのentityに対象のエンティティ(*_pn)があるかチェック
    reading_form_entities = [
        entity for entity in conv_dic["entity"].keys() if entity[-3:] == "_pn"
    ]
    try:
        if len(reading_form_entities) > 0:
            logger.info(
                f"This conversation add reading_form to {reading_form_entities}"
            )
            recoding_data = await get_recording_data(
                account_sid, recording_sid
            )
            await add_reading_form(
                conversation_ref, recoding_data, reading_form_entities
            )
    except Exception as e:
        ## 処理に失敗しても継続する
        logger.error(
            f"Error in add reading_form process. {e}", stack_info=True
        )

    gcs_path = await gcs_path_from_req(project_id, call_sid, customer_id)
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


async def get_customer_phone_number(account_sid: str, call_sid: str) -> str:
    """
    エンドユーザ電話番号(or SIP URI)をtwilio APIから取得する
    inboundの場合はfrom、outboundの場合はtoを取得する
    twilio APIから取得するので。SIP接続の場合はSIP URIが取得される

    Parameters
    ----------
    account_sid : str
        twilio APIにアクセスするためのAccount SID
    call_sid : str
        twilioのCall SID

    Returns
    -------
    エンドユーザ電話番号(or SIP URI) : str
    """
    twilio_account = await get_twilio_account(account_sid)
    auth_token = twilio_account.auth_token
    client = Client(account_sid, auth_token, http_client=custom_client)
    call = client.calls(call_sid).fetch()
    if call.direction == "inbound":
        return call.from_
    else:
        return call.to


async def get_aim_phone_number(
    account_sid: str, call_sid: str
) -> Tuple[str, str]:
    """
    AIMessenger電話番号(or SIP URI)と、架電方向(twilio側が受電かどうか)をtwilio APIから取得する
    inboundの場合はto、outboundの場合はfromを取得する
    twilio APIから取得するので。SIP接続の場合はSIP URIが取得される

    Parameters
    ----------
    account_sid : str
        twilio APIにアクセスするためのAccount SID
    call_sid : str
        twilioのCall SID

    Returns
    -------

    AIMessenger電話番号(or SIP URI) : str
    架電方向 : str
        inbound or outbound
    """
    twilio_account = await get_twilio_account(account_sid)
    auth_token = twilio_account.auth_token
    client = Client(account_sid, auth_token, http_client=custom_client)
    call = client.calls(call_sid).fetch()
    if call.direction == "outbound":
        return call.direction, call.from_
    else:
        return call.direction, call.to


def get_twilio_call_resource(
    twilio_account: TwilioAccount, call_sid: str
) -> Any:
    client = Client(
        twilio_account.account_sid,
        twilio_account.auth_token,
        http_client=custom_client,
    )
    call = client.calls(call_sid).fetch()
    return call


def delete_twilio_call_recording(
    twilio_account: TwilioAccount, recording_sid: str
) -> Any:
    try:
        client = Client(twilio_account.account_sid, twilio_account.auth_token)
        call = client.recordings(recording_sid).delete()
        logger.info(
            f"finish to delete twilio recording file. sid={recording_sid}"
        )
        return call
    except Exception as e:
        logger.error(
            f"Error in delete twilio recording file. {e}", stack_info=True
        )
        return None


def get_twilio_child_call_resources(
    twilio_account: TwilioAccount, parent_call_sid: str
) -> Any:
    client = Client(
        twilio_account.account_sid,
        twilio_account.auth_token,
        http_client=custom_client,
    )
    calls = client.calls.list(parent_call_sid=parent_call_sid, limit=20)
    return calls


def is_target_call(
    target_intent: str, exclude_intent: str, intentmap: dict[str, Any]
) -> bool:
    ## terget_intentが未設定の場合は対象とする
    is_target = target_intent == ""
    for target in target_intent.split(","):
        if target in intentmap.keys():
            is_target = True
            break

    for exclude in exclude_intent.split(","):
        if exclude in intentmap.keys():
            is_target = False
            break

    return is_target


async def set_fs_is_active_false(
    project_id: str,
    customer_phone_number: str,
    customer_id: str,
    call_sid: str,
    account_sid: str,
) -> Any:
    conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()

    project = await get_project(project_id)
    tenant_ref = firestore_client.collection(env).document(project.tenant_id)
    customer_ref = tenant_ref.collection("customers").document(customer_id)
    project_ref = customer_ref.collection("projects").document(project_id)
    conversation_ref = project_ref.collection("conversations").document(
        conversation_id
    )
    doc = conversation_ref.get()
    to_sip_uri = ""
    from_sip_uri = ""
    is_sip = False
    meta_sip_data = ""
    is_active = doc.to_dict()["is_active"]
    if is_active is True:
        logger.info(
            f"conversation_id: {conversation_id} set by recording callback."
        )
        fs_status = doc.to_dict()["status"]
        if fs_status == CS.FORWARDING:
            conversation_ref.update(
                {"status": CS.CUTOFF_BEFORE_TRANSFER, "is_active": False}
            )
        else:
            # 転送以外でis_activeがTrueのままここにくる可能性があるため
            logger.warning(
                "Unexpected is_active=True when recording callback."
            )
            conversation_ref.update({"is_active": False})

        direction, aim_phone_number = await get_aim_phone_number(
            account_sid, call_sid
        )
        if "sip" in doc.to_dict():
            to_sip_uri = doc.to_dict()["sip"]["to_sip_uri"]
            from_sip_uri = doc.to_dict()["sip"]["from_sip_uri"]
            aim_phone_number = project_ref.to_dict()["aim_phone_number"]
            is_sip = True
            meta_sip_data = json.dumps(
                {"sip_data": doc.to_dict()["sip"]}, ensure_ascii=False
            )
        call_log_schema = Call(
            project_id=project_id,
            tenant_id=project.tenant_id,
            conversation_id=conversation_id,
            call_sid=call_sid,
            customer_id=customer_id,
            aim_phone_number=aim_phone_number,
            customer_phone_number=customer_phone_number,
            to_sip_uri=to_sip_uri,
            from_sip_uri=from_sip_uri,
            is_sip=is_sip,
            direction=direction,
            status=ConversationStatus.cutoff_before_transfer.name,
            meta=meta_sip_data,
        )
        pubsub_driver.publish2pubsub(call_log_schema)
    return conversation_ref


async def gcs_path_from_req(
    project_id: str,
    call_sid: str,
    customer_id: str,
) -> str:
    project = await get_project(project_id)
    tenant = await get_tenant(project.tenant_id)
    subdomain = tenant.subdomain
    conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()
    return f"{subdomain}/{project_id}/{customer_id}/{conversation_id}/audio"


async def add_reading_form(
    conversation_ref: Any,
    recording_data: Any,
    reading_form_entities: List[str],
) -> None:
    docs = conversation_ref.collection("conversation_events").stream()

    for reading_form_entity in reading_form_entities:
        for doc in docs:
            current_dic = doc.to_dict()
            logger.debug(current_dic["entity"].keys())
            if reading_form_entity in current_dic["entity"].keys():
                user_uttr_start_ts = current_dic["created_at"]
                stt_result = current_dic["message"]
                # このeventsの次のevents(のts)を取得
                after_docs = (
                    conversation_ref.collection("conversation_events")
                    .where("created_at", ">", user_uttr_start_ts)
                    .order_by("created_at")
                    .limit(1)
                    .stream()
                )
                for after_doc in after_docs:
                    next_doc = after_doc.to_dict()
                    next_uttr_start_ts = next_doc["created_at"]
                    # 音声切り出し
                    start_time = conversation_ref.get().to_dict()["created_at"]
                    cut_start_yomi = user_uttr_start_ts - start_time
                    cut_end_yomi = next_uttr_start_ts - start_time
                    cut_audio = recording_data[
                        (cut_start_yomi.seconds * 8000) : (
                            cut_end_yomi.seconds * 8000
                        )  # ch = 1, fr = 8000で固定
                    ]
                    # 切り出した音声を読み取得APIにリクエスト
                    params = {
                        "audio": cut_audio.tolist(),  # json serializeできるリストに変換(ndarray, bytesはできないため)
                        "stt_result": stt_result,
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{stt_reading_form_url}/stt_reading_form/name",
                            json=params,
                        ) as resp:
                            result = await resp.json(content_type=None)
                    logger.info(f"stt_readiing_form_name_result:{result}")
                    c_doc = conversation_ref.get()
                    yomi_dic = c_doc.to_dict()["reading_form"]
                    if len(result["reading_form"]) == 0:
                        logger.warning("stt_reading_form returned no results.")
                        yomi_dic[reading_form_entity] = {
                            "transcriptions": result.get("transcriptions")
                        }  # 人名読みが取得できなくても認識結果はログに残す
                    else:
                        yomi_dic[reading_form_entity] = {
                            "stt_result": stt_result,
                            "reading_form": result["reading_form"][0],
                            "confidence": result["confidence"],
                            "transcriptions": result["transcriptions"],
                        }
                    conversation_ref.update({"reading_form": yomi_dic})
                    break  # after-docsはlimit(1)なので一周で終わるはずだが念の為
            else:
                continue


async def get_recording_data(account_sid: str, recording_sid: str) -> Any:
    twilio_account = await get_twilio_account(account_sid)
    auth_token = twilio_account.auth_token
    recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}"

    basic_user_and_pasword = base64.b64encode(
        f"{account_sid}:{auth_token}".encode("utf-8")
    )
    headers = {
        "Authorization": "Basic " + basic_user_and_pasword.decode("utf-8")
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(recording_url) as resp:
            recording_data = await resp.read()
        logger.info(f"finish download recording data.")
        with wave.open(io.BytesIO(recording_data), mode="rb") as wf:
            buf = wf.readframes(-1)  # すべてのデータを読み込む
        d = np.frombuffer(buf, dtype="int16")
        data_user = d[::2]

        return data_user


async def get_firestore_references(
    project_id: str,
    customer_id: str,
    conversation_id: str,
) -> Any:
    """
    Firestoreのdocument参照を取得する

    Parameters
    ----------
    project_id : str
        プロジェクトID
    customer_id : str
        顧客ID
    conversation_id : str
        会話ID

    Returns
    -------
    firestoreのdocument参照 : dict[str, Any]
        project: プロジェクト情報
        tenant_ref: テナント情報の参照
        customer_ref: 顧客情報の参照
        project_ref: プロジェクト情報の参照
        conversation_ref: 会話情報の参照
    """
    project = await get_project(project_id)
    tenant_ref = firestore_client.collection(env).document(project.tenant_id)
    customer_ref = tenant_ref.collection("customers").document(customer_id)
    project_ref = customer_ref.collection("projects").document(project_id)
    conversation_ref = project_ref.collection("conversations").document(
        conversation_id
    )
    return {
        "project": project,
        "tenant_ref": tenant_ref,
        "customer_ref": customer_ref,
        "project_ref": project_ref,
        "conversation_ref": conversation_ref,
    }


def is_sip_call(aim_phone_number_or_sipuri: str) -> bool:
    """
    aim_phone_numberの形式からSIP接続かどうかを判定する

    Parameters
    ----------
    aim_phone_number_or_sipuri : str
        twilio APIから取得したAIMessenger電話番号(or SIP URI)

    Returns
    -------
    SIP接続かどうか : bool
        true: SIP接続, false: 公衆回線接続
    """
    return "@" in aim_phone_number_or_sipuri
