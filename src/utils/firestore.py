import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

from .gcp import GCP


class Firestore(GCP):
    """Firestore接続用のクラス

     Firestore接続に必要な認証情報を取得しwriteをおこなう

    Attributes:
        env(str): 開発環境。['dev', 'stage', 'prod']

    """

    def __init__(self, env: str, gcp_project_id: str):
        super().__init__(env, gcp_project_id, "firestore")
        credential_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", None
        )

        if credential_path is not None:
            with open(credential_path) as f:
                cred = credentials.Certificate(json.load(f))
            firebase_admin.initialize_app(credential=cred)
        else:
            firebase_admin.initialize_app(credential=self.credentials)
        self.fs_client = firestore.client()


firestore_client = Firestore(
    os.environ["ENV"], os.environ["GCP_PROJECT_ID"]
).fs_client