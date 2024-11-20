import json
from fastapi import Form, Request, Response, status
from src.utils import gcs as gcs_service
from src.utils import get_custom_logger

logger = get_custom_logger(__name__)

@router.post("/twilio2gcs", tags=["/recording"])
async def post_twilio2gcs(
    request: Request,
    RecordingUrl: str = Form(...),
    RecordingSid: str = Form(...),
    AccountSid: str = Form(...),
    CallSid: str = Form(...),
) -> Response:
    
    gcs_path = await gcs_path_from_req(project_id, call_sid, customer_id)
    await gcs_service.twilio2gcs(
        recording_url,
        gcs_path,
        account_sid,
        custom_value=recording_sid,
    )
    logger.info(f"finish to copy wav file to gcs. path={gcs_path}")
    
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