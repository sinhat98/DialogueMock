import uuid
from typing import List

from sqlalchemy.dialects.mysql import TIMESTAMP as Timestamp
from sqlalchemy.future import select
from sqlalchemy.schema import Column
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.functions import current_timestamp
from sqlalchemy.types import String

from src.utils.db import Base, csqld, ma


class Tenant(Base):
    __tablename__ = "tenant"
    id = Column(String(50), primary_key=True)
    subdomain = Column(String(32))
    display_name = Column(String(255))
    created_at = Column(Timestamp, server_default=current_timestamp())
    updated_at = Column(
        Timestamp,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class TenantSchema(ma.Schema):
    class Meta:
        model = Tenant
        fields = (
            "id",
            "subdomain",
            "display_name",
            "created_at",
            "updated_at",
        )


class TenantAlreadyExistException(Exception):
    pass


class TenantNotFoundException(Exception):
    pass


class SubdomainAlreadyExistException(Exception):
    pass


async def exist_tenant_with_subdomain(subdomain: str) -> bool:
    session = await csqld.get_async_session()
    result = await session.execute(
        select(Tenant).filter(Tenant.subdomain == subdomain)
    )
    tenant = result.scalars().first()
    await session.close()
    return tenant is not None


async def exist_tenant_with_tenant_id(tenant_id: str) -> bool:
    session = await csqld.get_async_session()
    result = await session.execute(
        select(Tenant).filter(Tenant.id == tenant_id)
    )
    tenant = result.scalars().first()
    await session.close()
    return tenant is not None


async def get_tenant(tenant_id: str) -> Tenant:
    if not await exist_tenant_with_tenant_id(tenant_id):
        raise TenantNotFoundException
    session = await csqld.get_async_session()
    result = await session.execute(
        select(Tenant).filter(Tenant.id == tenant_id)
    )
    tenant = result.scalars().first()
    await session.close()
    return tenant


async def get_tenants() -> List[Tenant]:
    session = await csqld.get_async_session()
    result = await session.execute(select(Tenant))
    tenants = result.scalars().all()
    await session.close()
    return tenants


async def create_tenant(subdomain: str, display_name: str) -> Tenant:
    if await exist_tenant_with_subdomain(subdomain):
        raise SubdomainAlreadyExistException

    session = await csqld.get_async_session()
    tenant_id = str(uuid.uuid4())[0:8]
    tenant = Tenant(
        id=tenant_id, subdomain=subdomain, display_name=display_name
    )
    session.add(tenant)
    await session.commit()
    await session.close()
    return await get_tenant(tenant_id)


async def create_tenant_with_tenant_id(
    tenant_id: str,
    subdomain: str,
    display_name: str,
) -> Tenant:
    if len(tenant_id) != 8:
        raise ValueError
    if await exist_tenant_with_tenant_id(tenant_id):
        raise TenantAlreadyExistException
    if await exist_tenant_with_subdomain(subdomain):
        raise SubdomainAlreadyExistException
    session = await csqld.get_async_session()
    tenant = Tenant(
        id=tenant_id,
        subdomain=subdomain,
        display_name=display_name,
    )
    session.add(tenant)
    await session.commit()
    await session.close()
    return await get_tenant(tenant_id)


async def update_tenant(
    tenant_id: str, subdomain: str, display_name: str
) -> Tenant:
    if not await exist_tenant_with_tenant_id(tenant_id):
        raise TenantNotFoundException
    if await exist_tenant_with_subdomain(subdomain):
        raise SubdomainAlreadyExistException

    session = await csqld.get_async_session()
    result = await session.execute(
        select(Tenant).filter(Tenant.id == tenant_id)
    )
    tenant = result.scalars().first()
    tenant.subdomain = subdomain
    tenant.display_name = display_name
    session.add(tenant)
    await session.commit()
    await session.close()
    return await get_tenant(tenant_id)


async def delete_tenant(tenant_id: str) -> None:
    if not await exist_tenant_with_tenant_id(tenant_id):
        raise TenantNotFoundException

    session = await csqld.get_async_session()
    result = await session.execute(
        select(Tenant).filter(Tenant.id == tenant_id)
    )
    tenant = result.scalars().first()
    await session.delete(tenant)
    await session.commit()
    await session.close()
    return
