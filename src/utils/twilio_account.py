from sqlalchemy.future import select
from sqlalchemy.schema import Column
from sqlalchemy.types import String

import os



from voice_app.driver.gcp.cloud_sql import CloudSQL as CloudSQLDriver

from dotenv import load_dotenv

load_dotenv()




class TwilioAccount(Base):
    __tablename__ = "voice_twilio_account"
    account_sid = Column(String(50), primary_key=True)
    auth_token = Column(String(50))


class TwilioAccountSchema(ma.Schema):
    class Meta:
        model = "TwilioAccount"
        fields = ("account_sid", "auth_token")


class TwilioAccountAlreadyExistException(Exception):
    pass


class TwilioAccountNotFoundException(Exception):
    pass


async def exist_twilio_account(account_sid: str) -> bool:
    session = await csqld.get_async_session()
    result = await session.execute(
        select(TwilioAccount).filter(TwilioAccount.account_sid == account_sid)
    )
    twilio_account = result.scalars().first()
    await session.close()
    return twilio_account is not None


async def get_twilio_account(account_sid: str) -> TwilioAccount:
    if not await exist_twilio_account(account_sid):
        raise TwilioAccountNotFoundException
    session = await csqld.get_async_session()
    result = await session.execute(
        select(TwilioAccount).filter(TwilioAccount.account_sid == account_sid)
    )
    twilio_account = result.scalars().first()
    await session.close()
    return twilio_account


async def create_twilio_account(
    account_sid: str, auth_token: str
) -> TwilioAccount:
    if await exist_twilio_account(account_sid):
        raise TwilioAccountAlreadyExistException

    session = await csqld.get_async_session()
    twilio_account = TwilioAccount(
        account_sid=account_sid, auth_token=auth_token
    )
    session.add(twilio_account)
    await session.commit()
    await session.close()
    return await get_twilio_account(account_sid)


async def delete_twilio_account(account_sid: str) -> None:
    if not await exist_twilio_account(account_sid):
        raise TwilioAccountNotFoundException

    session = await csqld.get_async_session()
    result = await session.execute(
        select(TwilioAccount).filter(TwilioAccount.account_sid == account_sid)
    )
    twilio_account = result.scalars().first()
    await session.delete(twilio_account)
    await session.commit()
    await session.close()
    return
