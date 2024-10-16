import hashlib
import uuid
from src.utils.firestore import FirestoreClient
from src.utils import get_custom_logger
from google.cloud.firestore import SERVER_TIMESTAMP

logger = get_custom_logger(__name__)
# 初期化
firestore_client = FirestoreClient()

# 環境とIDの設定
ENV = "dev"  # 開発環境に合わせて変更
TENANT_ID = "outbound-test1-7yo16"
CUSTOMER_PHONE_NUMBER = "+815058105614"
CUSTOMER_ID = hashlib.sha1(CUSTOMER_PHONE_NUMBER.encode()).hexdigest()
PROJECT_ID = "Pcp6kf14ispc751svnjb0"

# ダミーのCall SIDとConversation IDを生成
def generate_dummy_call_sid():
    random_uuid = uuid.uuid4().hex
    call_sid = f'CA{random_uuid[:32]}'
    return call_sid

call_sid = generate_dummy_call_sid()
conversation_id = hashlib.sha1(call_sid.encode()).hexdigest()
logger.info(f"Conversation ID: {conversation_id}")
# Firestoreの参照を取得
tenant_ref = firestore_client.get_tenant_ref(ENV, TENANT_ID)
logger.info(f"Tenant ref: {tenant_ref.path}")
# 顧客データを作成または取得
customer_data = {
    "developer": False,
    "disabled": False,
    "display_name": "",
    "note": "",
    "preview": False,
    "voice": {"customer_phone_number": CUSTOMER_PHONE_NUMBER, "note": ""},
    "updated_at": SERVER_TIMESTAMP,
}
customer_ref = firestore_client.create_customer(tenant_ref, CUSTOMER_ID, customer_data)
logger.info(f"Customer ref: {customer_ref.path}")

# プロジェクトの参照を取得
project_ref = firestore_client.get_project_ref(customer_ref, PROJECT_ID)
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
    "created_at": SERVER_TIMESTAMP,
    "conversation_status": "left",
    "for_query": {
        "env": ENV,
        "tenant_id": TENANT_ID,
        "customer_id": CUSTOMER_ID,
        "project_id": PROJECT_ID,
        "customer_phone_number": CUSTOMER_PHONE_NUMBER,
        "conversation_id": conversation_id,
    },
    "reading_form": {},
}

# 対話ドキュメントを作成
conversation_ref = firestore_client.create_conversation(project_ref, conversation_id, conversation_data)
logger.info(f"Conversation ref: {conversation_ref.path}")

# 対話イベントを追加
event_data = {
    "message": "こんにちは、何をお手伝いできますか？",
    "sender_type": "bot",
    "entity": {},
    "is_ivr": False,
    "created_at": SERVER_TIMESTAMP,
}
event_id = firestore_client.add_conversation_event(conversation_ref, event_data)

# # 対話イベントを更新
# update_data = {
#     "entity": {"user_response": "口座の残高を知りたい"},
# }
# firestore_client.update_conversation_event(conversation_ref, event_id, update_data)

costomer_utterance = "口座の残高を知りたい"
event_data = {
    "message": costomer_utterance,
    "sender_type": "customer",
    "entity": {},
    "is_ivr": False,
    "created_at": SERVER_TIMESTAMP,
}
event_id = firestore_client.add_conversation_event(conversation_ref, event_data)

# 対話イベントを取得
events = firestore_client.get_conversation_events(conversation_ref)
for event in events:
    print(event)