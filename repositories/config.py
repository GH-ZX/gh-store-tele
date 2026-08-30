from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute
from models.app_config import AppConfig


class AppConfigRepository:
    @staticmethod
    async def get_by_key(key: str, session: AsyncSession | Session) -> AppConfig | None:
        stmt = select(AppConfig).where(AppConfig.key == key)
        result = await session_execute(stmt, session)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession | Session) -> list[AppConfig]:
        stmt = select(AppConfig).order_by(AppConfig.key)
        result = await session_execute(stmt, session)
        return list(result.scalars().all())

    @staticmethod
    async def create(key: str, value: str | None, is_secret: bool, description: str | None,
                     session: AsyncSession | Session) -> AppConfig:
        row = AppConfig(key=key, value=value, is_secret=is_secret, description=description)
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def update(config: AppConfig, session: AsyncSession | Session) -> None:
        session.add(config)
        await session.flush()
