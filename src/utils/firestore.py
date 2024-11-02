import os
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client, SERVER_TIMESTAMP
from src.utils import ROOT_DIR, get_custom_logger
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


load_dotenv()

logger = get_custom_logger(__name__)

# logger.info(f"ROOT_DIR: {ROOT_DIR}")

class FirestoreClient:
    """Firestoreに接続し、対話ログを管理するためのクラス"""

    def __init__(self):
        """
        コンストラクタ。Firestoreクライアントを初期化する。

        Args:
            credential_path (Optional[str]): サービスアカウント鍵のパス。環境変数で設定されていない場合に使用。
        """
        if not firebase_admin._apps:
            credential_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)
            if credential_path is not None:
                with open(credential_path) as f:
                    cred = credentials.Certificate(json.load(f))
                firebase_admin.initialize_app(credential=cred)
            # credential = self.get_credentials()
            # if credential is not None:
            #     logger.info(f"Use service account credential file. {credential}")
            #     firebase_admin.initialize_app(credential)
            # else:
            #     firebase_admin.initialize_app()
        
        self.client: Client = firestore.client()
        self.conversation_ref = None
    
    def get_credentials(self) -> Credentials:
        credential_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", None
        )
        return (
            Credentials.from_service_account_file(credential_path)
            if credential_path is not None
            else None
        )
        
    
    def get_timestamp(self):
        return SERVER_TIMESTAMP

    def get_tenant_ref(self, env: str, tenant_id: str):
        """テナントのドキュメント参照を取得"""
        return self.client.collection(env).document(tenant_id)

    def get_customer_ref(self, tenant_ref, customer_id: str):
        """顧客のドキュメント参照を取得"""
        return tenant_ref.collection("customers").document(customer_id)

    def get_project_ref(self, customer_ref, project_id: str):
        """プロジェクトのドキュメント参照を取得"""
        return customer_ref.collection("projects").document(project_id)

    def set_conversation_ref(self, project_ref, conversation_id: str):
        """対話のドキュメント参照を取得"""
        self.conversation_ref = project_ref.collection("conversations").document(conversation_id)
        logger.info(f"[Set Conversation Ref] Conversation ref: {self.conversation_ref.path}")

    def create_customer(self, tenant_ref, customer_id: str, customer_data: Dict[str, Any]):
        """顧客ドキュメントを作成"""
        customer_ref = self.get_customer_ref(tenant_ref, customer_id)
        if not customer_ref.get().exists:
            customer_ref.set(customer_data)
        return customer_ref

    def create_conversation(self, conversation_data: Dict[str, Any]):
        """対話ドキュメントを作成"""
        self.conversation_ref.set(conversation_data)
        logger.info(f"[Create Conversation] Conversation ref: {self.conversation_ref.path}")

    def add_conversation_event(self, event_data: Dict[str, Any]):
        """対話イベントを追加"""
        event_id = str(uuid.uuid4()).replace("-", "")
        event_ref = self.conversation_ref.collection("conversation_events").document(event_id)
        event_ref.set(event_data)
        logger.info(f"[Add Event] Event ref: {event_ref.path}")
        return event_id

    def update_conversation_event(self, conversation_ref, event_id: str, update_data: Dict[str, Any]):
        """対話イベントを更新"""
        event_ref = conversation_ref.collection("conversation_events").document(event_id)
        event_ref.update(update_data)

    def get_conversation_events(self, conversation_ref):
        """対話イベントを取得"""
        events = conversation_ref.collection("conversation_events").order_by("created_at").stream()
        return [event.to_dict() for event in events]