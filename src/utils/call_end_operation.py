from typing import List

from sqlalchemy.dialects.mysql import TIMESTAMP as Timestamp
from sqlalchemy.future import select
from sqlalchemy.schema import Column
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.functions import current_timestamp
from sqlalchemy.types import String, Text

from src.utils.db import Base, ma, csqld



class CallendOperation(Base):
    __tablename__ = "voice_callend_operation"
    id = Column(String(50), primary_key=True)
    project_id = Column(String(21))
    exec_function_name = Column(String(255))
    target_intent = Column(Text)
    exclude_intent = Column(Text)
    note = Column(Text)
    created_at = Column(Timestamp, server_default=current_timestamp())
    updated_at = Column(
        Timestamp,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class CallendOperationSchema(ma.Schema):
    class Meta:
        model = CallendOperation
        fields = (
            "id",
            "project_id",
            "exec_function_name",
            "target_intent",
            "exclude_intent",
            "note",
            "created_at",
            "updated_at",
        )


class CallendOperationNotFoundException(Exception):
    pass


# TODO: 使っていない？
# async def get_by_id(tenant_id: str, id: str) -> CallendOperation:
#     session = await csqld.get_async_session(csqld.tenant_scheme_ref(tenant_id))
#     result = await session.execute(select(CallendOperation).filter(CallendOperation.id == id))
#     res = result.scalars().first()
#     session.close()
#
#     if res is None:
#         raise CallendOperationNotFoundException
#     return res


async def list_by_project_id(
    tenant_id: str, project_id: str, is_strict: bool = False
) -> List[CallendOperation]:
    session = await csqld.get_async_session(csqld.tenant_scheme_ref(tenant_id))
    result = await session.execute(
        select(CallendOperation).filter(
            CallendOperation.project_id == project_id
        )
    )
    res = result.scalars().all()
    await session.close()

    if res is None and is_strict:
        raise CallendOperationNotFoundException
    return res
