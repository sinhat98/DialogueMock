import os

from google.oauth2.service_account import Credentials


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