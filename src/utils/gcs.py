import base64
import os
import urllib.request

from src.utils.gcp import GCS as GCSDriver
from src.utils.twilio_account import TwilioAccount

from dotenv import load_dotenv

load_dotenv()

ENV = str(os.environ.get("ENV"))
GCP_PROJECT_ID = str(os.environ.get("GCP_PROJECT_ID"))
BUCKET_NAME = str(os.environ.get("RECORDING_BUCKET_NAME"))
TWILIO_AUTH_TOKEN = str(os.environ.get("TWILIO_AUTH_TOKEN"))
gcs_driver = GCSDriver(ENV, GCP_PROJECT_ID)


async def twilio2gcs(
    recording_url: str,
    gcs_path: str,
    account_sid: str,
    custom_key: str = "recordingSid",
    custom_value: str = "",
) -> None:
    """twilioのレコーディング内容をGCSに保存する
    Args:
        recording_url: Twilioのrecording url
        gcs_path: 保存先のGCSのパス
        account_sid: Basic認証を行うためのAccountSID
        custom_key: gcsオブジェクトのカスタムメタデータ.key
        custom_value: gcsオブジェクトのカスタムメタデータ.value

    Returns:
        None
    """
    twilio_account = TwilioAccount(account_sid, TWILIO_AUTH_TOKEN)
    auth_token = twilio_account.auth_token

    basic_user_and_pasword = base64.b64encode(
        "{}:{}".format(account_sid, auth_token).encode("utf-8")
    )
    headers = {
        "Authorization": "Basic " + basic_user_and_pasword.decode("utf-8")
    }
    recording_url_add_header = urllib.request.Request(
        url=recording_url, headers=headers
    )
    with urllib.request.urlopen(recording_url_add_header) as web_file:
        recording_data = web_file.read()

    blob_name = f"{gcs_path}.wav"
    bucket = gcs_driver.get_bucket(BUCKET_NAME)

    gcs_driver.upload_from_string_with_custom_metadata(
        data=recording_data,
        blob_name=blob_name,
        bucket=bucket,
        custom_key=custom_key,
        custom_value=custom_value,
    )
