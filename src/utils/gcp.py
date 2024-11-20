import os
from typing import BinaryIO
from google.cloud.storage import Bucket, Client
from google.oauth2.service_account import Credentials
from src.utils import get_custom_logger


env = os.environ["ENV"]
gcp_project_id = os.environ["GCP_PROJECT_ID"]


logger = get_custom_logger(__name__)

class GCP:
    """GCP接続用のクラス
     GCP接続に必要な認証情報を取得するクラス。
     各サービスに継承して利用
    Attributes:
        env(str): 開発環境。['stage', 'prod']
        service(str): 接続を行うGCPサービス。['bigquery', 'storage', 'firestore', 'cloudsql_mysql', 'nlu']
        project_id(str): GCPのプロジェクトID
        credentials(Credentials): GCPのサービスへの認証情報
    """

    def __init__(self, env: str, project_id: str, service: str):
        """コンストラクタ
        クラスの初期化
        Args:
            env(str): 開発環境。['stage', 'prod']
            service: 接続を行うGCPサービス。['bigquery']
        """
        self.env = env
        self.project_id = project_id
        self.service = service
        self.credentials = self.get_credentials()

    def get_credentials(self) -> Credentials:
        credential_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", None
        )
        return (
            Credentials.from_service_account_file(credential_path)
            if credential_path is not None
            else None
        )
class GCS(GCP):
    """Storage接続用のクラス
     Storage接続に必要な認証情報を取得しreadをおこなう
    Attributes:
        env(str): 開発環境。['stage', 'prod']
        service(str): 接続を行うGCPサービス。(このクラスでは'storage'のみ利用)
        project_id(str): GCPのプロジェクトID
        credentials(Credentials): GCPのサービスへの認証情報
    """

    def __init__(self, env: str, project_id: str):
        super().__init__(env, project_id, "storage")
        self.client = Client(credentials=self.credentials)

    def get_bucket(self, bucket_name: str) -> Bucket:
        return self.client.get_bucket(bucket_name)

    def upload_from_filename(
        self, file_path: str, blob_name: str, bucket: Bucket
    ) -> None:
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(file_path)

    def upload_from_file(
        self, file: BinaryIO, blob_name: str, bucket: Bucket
    ) -> None:
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file)

    def upload_from_string(
        self, data: str, blob_name: str, bucket: Bucket
    ) -> None:
        blob = bucket.blob(blob_name)
        blob.upload_from_string(data)

    def upload_from_string_with_custom_metadata(
        self,
        data: str,
        blob_name: str,
        bucket: Bucket,
        custom_key: str,
        custom_value: str,
    ) -> None:
        blob = bucket.blob(blob_name)
        metadata = {custom_key: custom_value}
        blob.metadata = metadata
        blob.upload_from_string(data)

