import uuid
from typing import List

from sqlalchemy.dialects.mysql import TIMESTAMP as Timestamp
from sqlalchemy.future import select
from sqlalchemy.schema import Column
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.functions import current_timestamp
from sqlalchemy.types import String

from src.utils.db import Base, csqld, ma


class Project(Base):
    __tablename__ = "project"
    id = Column(String(50), primary_key=True)
    display_name = Column(String(255))
    tenant_id = Column(String(255))
    created_at = Column(Timestamp, server_default=current_timestamp())
    updated_at = Column(
        Timestamp,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class ProjectSchema(ma.Schema):
    class Meta:
        model = Project
        fields = (
            "id",
            "display_name",
            "tenant_id",
            "created_at",
            "updated_at",
        )


class ProjectNotFoundException(Exception):
    pass


class DisplayNameAlreadyExistException(Exception):
    pass


async def exist_project_with_display_name(display_name: str) -> bool:
    session = await csqld.get_async_session()
    result = await session.execute(
        select(Project).filter(Project.display_name == display_name)
    )
    project = result.scalars().first()
    await session.close()
    return project is not None


async def exist_project_with_project_id(project_id: str) -> bool:
    session = await csqld.get_async_session()
    result = await session.execute(
        select(Project).filter(Project.id == project_id)
    )
    project = result.scalars().first()
    await session.close()
    return project is not None


async def get_project(project_id: str) -> Project:
    if not await exist_project_with_project_id(project_id):
        raise ProjectNotFoundException
    session = await csqld.get_async_session()
    result = await session.execute(
        select(Project).filter(Project.id == project_id)
    )
    project = result.scalars().first()
    await session.close()
    return project


async def get_projects() -> List[Project]:
    session = await csqld.get_async_session()
    result = await session.execute(select(Project))
    projects = result.scalars().all()
    await session.close()
    return projects


async def create_project(display_name: str, tenant_id: str) -> Project:
    if await exist_project_with_display_name(display_name):
        raise DisplayNameAlreadyExistException

    session = await csqld.get_async_session()
    project_id = str(uuid.uuid4())[0:8]
    project = Project(
        id=project_id, display_name=display_name, tenant_id=tenant_id
    )
    session.add(project)
    await session.commit()
    await session.close()
    return await get_project(project_id)


async def delete_project(project_id: str) -> None:
    if not await exist_project_with_project_id(project_id):
        raise ProjectNotFoundException

    session = await csqld.get_async_session()
    result = await session.execute(
        select(Project).filter(Project.id == project_id)
    )
    project = result.scalars().first()
    await session.delete(project)
    await session.commit()
    await session.close()
    return
