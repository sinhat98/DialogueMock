

from dataclasses import dataclass

@dataclass
class TwilioAccount:
    account_sid: str
    auth_token: str


async def get_twilio_account() -> TwilioAccount:
    pass








