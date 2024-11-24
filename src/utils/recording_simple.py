import os
from fastapi import APIRouter, Form, Request, Response, status
from src.utils import gcs as gcs_service
from src.utils.twilio_account import get_twilio_account, TwilioAccount
from src.utils.firestore import FirestoreClient
from src.utils import get_custom_logger
from twilio.rest import Client

from dotenv import load_dotenv
from typing import Any

import json
import hashlib

load_dotenv()

logger = get_custom_logger(__name__)

firestore_client = FirestoreClient().client

router = APIRouter()

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
    customer_id = hashlib.sha1(customer_phone_number.encode()).hexdigest()
    conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()
    

    customer_phone_number = "+" + customer_phone_number
    
    # conversation_ref = firestore_client.collection("projects").document(
    #     project_id
    # ).collection("customers").document(customer_id).collection("conversations").document(conversation_id).hexdigest()
    

    # # conversationのentityに対象のエンティティ(*_pn)があるかチェック
    # reading_form_entities = [
    #     entity for entity in conv_dic["entity"].keys() if entity[-3:] == "_pn"
    # ]
    # try:
    #     if len(reading_form_entities) > 0:
    #         logger.info(
    #             f"This conversation add reading_form to {reading_form_entities}"
    #         )
    #         recoding_data = await get_recording_data(
    #             account_sid, recording_sid
    #         )
    #         await add_reading_form(
    #             conversation_ref, recoding_data, reading_form_entities
    #         )
    # except Exception as e:
    #     ## 処理に失敗しても継続する
    #     logger.error(
    #         f"Error in add reading_form process. {e}", stack_info=True
    #     )
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
        logger.info(
            f"finish to delete twilio recording file. sid={recording_sid}"
        )
        return call
    except Exception as e:
        logger.error(
            f"Error in delete twilio recording file. {e}", stack_info=True
        )
        return None