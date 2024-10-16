import os
import time
import dataclasses
import datetime
import json
import re
from dataclasses import asdict, dataclass
from enum import Enum, auto

from typing import Optional, BinaryIO, List, Dict, Any

import sqlalchemy
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool



from google.api_core.future import Future
from google.cloud.pubsub_v1 import PublisherClient

from voice_app.models.ab_test import AppliedLogic

env = os.environ["ENV"]
gcp_project_id = os.environ["GCP_PROJECT_ID"]

from google.cloud.storage import Bucket, Client


from google.oauth2.service_account import Credentials

from src.utils import get_custom_logger

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
        
class CloudSQL(GCP):
    """CloduSQL for MySQL接続用のクラス
     DB接続に必要な認証情報を取得しread/writeをおこなう
    Attributes:
        env(str): 開発環境。['stage', 'prod']
        service(str): 接続を行うGCPサービス。(このクラスでは'cloudsql_mysql'のみ利用)
        project_id(str): GCPのプロジェクトID
        credentials(Credentials): GCPのサービスへの認証情報
        db_setting(Dict[str]): DBの接続情報
        host: dbのホスト名
        protocol: dbアクセスのプロトコル。['tcp', 'unix_domain_socket']
        port: dbのport(デフォルト3308)
    """

    def __init__(
        self,
        env: str,
        project_id: str,
        protocol: str,
        db_user: str,
        db_pass: str,
        host: str,
        port: str = "3308",
        db_name: str | None = None,
    ):
        super().__init__(env, project_id, "cloudsql_mysql")
        self.db_setting = {
            "drivername": "mysql+pymysql",
            "username": db_user,
            "password": db_pass,
        }
        self.async_db_setting = {
            "drivername": "mysql+asyncmy",
            "username": db_user,
            "password": db_pass,
        }
        if db_name is not None:
            self.db_setting["database"] = db_name
        self.host = host
        self.protocol = protocol
        self.port = port
        self.db_name = db_name
        self.engine = self.get_engine()
        self.async_engine = self.get_async_engine()

    def get_engine(self, db_name: str | None = None) -> sqlalchemy.engine:
        """CloudSQL for MySQLのconnecionを取得
        Returns:
            sqlalchemy.engine: dbのconnection
        """
        if self.protocol == "unix_domain_socket":
            query = {"unix_socket": f"/cloudsql/{self.host}"}
            url = URL(**self.db_setting, query=query)
        elif self.protocol == "tcp":
            url = "{drivername}://{username}:{password}@{host}:{port}".format(
                **self.db_setting, host=self.host, port=self.port
            )
            if db_name is not None:
                url = f"{url}/{db_name}"
            elif self.db_name is not None:
                url = f"{url}/{self.db_name}"
        else:
            raise ValueError("protocol must be unix_domain_socket or tcp.")

        engine = create_engine(
            url,
            pool_size=30,
            max_overflow=10,
            pool_timeout=30,  # 30 seconds
            pool_recycle=590,  # 10 minutes
            pool_pre_ping=True,
        )

        return engine

    def get_async_engine(
        self, db_name: Optional[str] = None
    ) -> sqlalchemy.engine:
        """CloudSQL for MySQLのasync connecionを取得
        Returns:
            sqlalchemy.async_engine: dbのasync connection
        """
        if self.protocol == "unix_domain_socket":
            query = {"unix_socket": f"/cloudsql/{self.host}"}
            url = URL(**self.async_db_setting, query=query)
        elif self.protocol == "tcp":
            url = "{drivername}://{username}:{password}@{host}:{port}".format(
                **self.async_db_setting, host=self.host, port=self.port
            )
            if db_name is not None:
                url = f"{url}/{db_name}"
            elif self.db_name is not None:
                url = f"{url}/{self.db_name}"
        else:
            raise ValueError("protocol must be unix_domain_socket or tcp.")

        engine = create_async_engine(
            url, pool_pre_ping=True, poolclass=NullPool
        )

        return engine

    @staticmethod
    def common_scheme_ref(env = "dev") -> str:
        db_name = f"{env}_common"
        return db_name

    @staticmethod
    def project_scheme_ref(project_id: str, env = "dev") -> str:
        db_name = f"{env}_{project_id}"
        return db_name

    @staticmethod
    def tenant_scheme_ref(tenant_id: str, env="dev") -> str:
        return f"`{env}_tenant_{tenant_id}`"

    def get_session(self, db_name: Optional[str] = None) -> Session:
        if db_name is None:
            db_name = self.common_scheme_ref()

        retry_count = 0

        while True:
            try:
                session = sessionmaker(self.engine)()
                query = f"USE {db_name}"
                logger.info(query)
                session.execute(query)
                break
            except Exception as e:
                retry_count += 1
                if retry_count > 5:
                    raise e
                logger.info("lost DB connection. retry create session.")
                time.sleep(1)

        return session

    async def get_async_session(
        self, db_name: Optional[str] = None
    ) -> AsyncSession:
        if db_name is None:
            db_name = self.common_scheme_ref()

        retry_count = 0

        while True:
            try:
                async_session = sessionmaker(
                    bind=self.async_engine, class_=AsyncSession
                )()
                query = f"USE {db_name}"
                await async_session.execute(query)
                break
            except Exception as e:
                retry_count += 1
                if retry_count > 5:
                    raise e
                logger.info("lost DB connection. retry create session.")
                time.sleep(1)

        return async_session


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



def toCamelCase(string: str, titleCase: bool = False) -> str:
    if titleCase:
        return "".join(x.title() for x in string.split("_"))
    else:
        return re.sub("_(.)", lambda m: m.group(1).upper(), string.lower())


class ConversationStatus(Enum):
    disabled = auto()  # anonymous_callなどの架電不能
    error = auto()  # VoiceBot内でのエラーによって切断
    calling = auto()  # 架電開始＆架電中
    register = auto()  # 架電予約
    ringing = auto()  # 呼び出し中
    not_pick_up = auto()  # 電話に出なかった
    success = auto()  # ストーリーの最後まで進んで終了
    voice_mail = auto()  # 留守電
    cutoff = auto()  # 通話がストーリーの途中で切られる
    busy = auto()  # 架電または転送したがビジーの場合
    transfer = auto()  # 転送
    transfer_busy = auto()  # 転送したがビジーの場合
    transfer_success = auto()  # 転送後、架電成功
    transfer_not_pick_up = auto()  # 転送後電話に出なかった
    transfer_voice_mail = auto()  # 転送後留守電
    cutoff_before_transfer = auto()  # 転送処理に入ったが転送前に切断された
    failed = auto()  # 転送後留守電


class SenderType(Enum):
    customer = auto()
    bot = auto()


# publish2pubsubの型ヒントのためのsuperクラス。
@dataclass
class LogSchema:
    # 会話中不変
    # tenant_idだが、既存のDataFlowに合わせるためproject_idが必要
    project_id: str = dataclasses.field(init=False)
    tenant_id: str = dataclasses.field(init=False)
    aim_phone_number: str = dataclasses.field(init=False)
    customer_phone_number: str = dataclasses.field(init=False)
    direction: Optional[str] = dataclasses.field(init=False)
    customer_id: str = dataclasses.field(init=False)
    call_sid: str = dataclasses.field(init=False)
    conversation_id: str = dataclasses.field(init=False)
    log_name: str = dataclasses.field(init=False)
    log_version: str = dataclasses.field(init=False)
    # SIP用の発信・着信者情報
    to_sip_uri: str = dataclasses.field(init=False)
    from_sip_uri: str = dataclasses.field(init=False)
    is_sip: bool = dataclasses.field(init=False)

    # 会話中可変
    timestamp: int = dataclasses.field(init=False)
    meta: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.project_id = ""
        self.tenant_id = ""
        self.aim_phone_number = ""
        self.customer_phone_number = ""
        self.customer_id = ""
        self.direction = ""
        self.conversation_id = ""
        self.call_sid = ""
        self.log_name = (
            f"{env}-metrics.voice-{self.__class__.__name__.lower()}"
        )
        self.log_version = os.environ["PUBSUB_LOG_VERSION"]
        self.to_sip_uri = ""
        self.from_sip_uri = ""
        self.is_sip = False
        self.timestamp = int(datetime.datetime.now().timestamp() * 1000)
        self.meta = ""

    def to_json(self) -> str:
        old_dict = asdict(self)
        new_dict = {}
        for k, v in old_dict.items():
            cameled_key = toCamelCase(k)
            new_dict[cameled_key] = v
        return json.dumps(new_dict, ensure_ascii=False)


@dataclass
class Call(LogSchema):
    status: str = dataclasses.field(init=False)

    def __init__(
        self,
        project_id: str,
        tenant_id: str,
        conversation_id: str,
        aim_phone_number: str,
        customer_phone_number: str,
        to_sip_uri: str,
        from_sip_uri: str,
        is_sip: bool,
        customer_id: str,
        call_sid: str,
        direction: str,
        status: str,
        meta: str,
    ) -> None:
        super(Call, self).__init__()
        self.project_id = project_id
        self.tenant_id = tenant_id
        self.conversation_id = conversation_id
        self.aim_phone_number = aim_phone_number
        self.customer_phone_number = customer_phone_number
        self.to_sip_uri = to_sip_uri
        self.from_sip_uri = from_sip_uri
        self.is_sip = is_sip
        self.customer_id = customer_id
        self.call_sid = call_sid
        self.direction = direction
        self.status = status
        self.meta = meta


@dataclass
class Message(LogSchema):
    request_id: str = dataclasses.field(init=False)
    message: str = dataclasses.field(init=False)
    sender_type: str = dataclasses.field(init=False)
    ab_log: List[AppliedLogic]

    def __init__(
        self,
        project_id: str,
        tenant_id: str,
        conversation_id: str,
        call_sid: str,
        customer_id: str,
        aim_phone_number: str,
        customer_phone_number: str,
        to_sip_uri: str,
        from_sip_uri: str,
        is_sip: bool,
        direction: str,
        ab_log: List[AppliedLogic],
    ) -> None:
        super(Message, self).__init__()
        self.project_id = project_id
        self.tenant_id = tenant_id
        self.conversation_id = conversation_id
        self.aim_phone_number = aim_phone_number
        self.customer_phone_number = customer_phone_number
        self.to_sip_uri = to_sip_uri
        self.from_sip_uri = from_sip_uri
        self.is_sip = is_sip
        self.customer_id = customer_id
        self.call_sid = call_sid
        self.direction = direction
        self.ab_log = ab_log

class PubSub(GCP):
    def __init__(self) -> None:
        super().__init__(env, gcp_project_id, "pubsub")
        self.topic_id = os.environ["PUBSUB_TOPICID"]
        self.publisher = PublisherClient()
        self.topic_path = self.publisher.topic_path(
            self.project_id, self.topic_id
        )

    def publish2pubsub(self, data: LogSchema) -> Future:
        data.timestamp = int(datetime.datetime.now().timestamp() * 1000)
        jsoned_data = data.to_json()
        encoded_data = jsoned_data.encode("utf-8")
        future = self.publisher.publish(
            self.topic_path,
            encoded_data,
            origin=__name__,
            username="voice-app",
        )
        # 可変のmetaを初期化
        data.meta = ""
        return future
