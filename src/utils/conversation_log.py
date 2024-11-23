
import pandas as pd
from datetime import datetime

import os

import json

from src.utils.gcp import GCS as GCSDriver
from src.utils import get_custom_logger

logger = get_custom_logger(__name__)

from dotenv import load_dotenv

load_dotenv()

ENV = str(os.environ.get("ENV"))
GCP_PROJECT_ID = str(os.environ.get("GCP_PROJECT_ID"))
BUCKET_NAME = str(os.environ.get("RECORDING_BUCKET_NAME"))
TWILIO_AUTH_TOKEN = str(os.environ.get("TWILIO_AUTH_TOKEN"))
gcs_driver = GCSDriver(ENV, GCP_PROJECT_ID)


# DataFrameのスキーマを定義
CONVERSATION_LOG_SCHEMA = [
    'timestamp',      # 発話のタイムスタンプ
    'speaker',        # 発話者（'bot', 'customer'）
    'message',        # 発話内容やイベントの詳細
    'intent',         # DSTの状態
    # DST関連の追加フィールド
    'dialogue_state', # 対話の状態
    'current_slot',   # 現在のスロット状態
    'previous_slot',  # 前回のスロット状態
    'missing_slots',  # 未入力の必須スロット
    'updated_slots',  # 更新されたスロット
    'required_slots', # 必須スロット
    'optional_slots', # オプションのスロット
    'correction_slot' # 訂正中のスロット
]

def parse_dst_state(dst_state: dict) -> dict:
    """DST状態を整形された辞書に変換する"""
    return {
        'intent': dst_state.get('intent'),
        'dialogue_state': dst_state.get('dialogue_state'),
        'state': json.dumps(dst_state.get('state', {}), ensure_ascii=False),
        'previous_state': json.dumps(dst_state.get('previous_state', {}), ensure_ascii=False),
        'missing_slots': json.dumps(dst_state.get('missing_slots', []), ensure_ascii=False),
        'updated_slots': json.dumps(dst_state.get('updated_slots', []), ensure_ascii=False),
        'required_slots': json.dumps(dst_state.get('required_slots', []), ensure_ascii=False),
        'optional_slots': json.dumps(dst_state.get('optional_slots', []), ensure_ascii=False),
        'correction_slot': dst_state.get('correction_slot')
    }

class ConversationLogger:
    def __init__(self, call_sid: str):
        self.df = pd.DataFrame(columns=CONVERSATION_LOG_SCHEMA)
        self.call_sid = call_sid
        
    def add_log_entry(
        self,
        speaker: str,
        message: str,
        dst_state: dict = None,
    ) -> None:
        """会話ログにエントリーを追加する"""
        new_entry = {
            'timestamp': datetime.now(),
            'speaker': speaker,
            'message': message,
        }

        # DST状態がある場合は追加
        if dst_state:
            parsed_dst = parse_dst_state(dst_state)
            new_entry.update(parsed_dst)

        self.df = pd.concat([self.df, pd.DataFrame([new_entry])], ignore_index=True)
        
    def to_csv(self, file_path) -> str:
        """会話ログをCSV形式で保存する"""
        return self.df.to_csv(file_path, index=False)


    async def save_conversation_log_to_gcs(
        self,
        gcs_path: str,
    ) -> None:
        """会話ログのDataFrameをCSV形式でGCSに保存する
        Args:
            conversation_log: 保存する会話ログのDataFrame
            gcs_path: 保存先のGCSのパス
            call_sid: 通話のID

        Returns:
            None
        """
        try:
            # DataFrameをCSV文字列に変換
            csv_data = self.df.to_csv(index=False).encode('utf-8')
            
            # GCSのパスを構築
            blob_name = f"{gcs_path}/{self.call_sid}.csv"
            bucket = gcs_driver.get_bucket(BUCKET_NAME)

            # GCSにアップロード
            gcs_driver.upload_from_string_with_custom_metadata(
                data=csv_data,
                blob_name=blob_name,
                bucket=bucket,
                custom_key="callSid",
                custom_value=self.call_sid,
            )
            
            logger.info(f"Successfully saved conversation log to GCS: {blob_name}")
        except Exception as e:
            logger.error(f"Failed to save conversation log to GCS: {str(e)}", exc_info=True)