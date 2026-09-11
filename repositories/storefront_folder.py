from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.storefront_folder import StorefrontFolder, StorefrontFolderDTO


class StorefrontFolderRepository:
    @staticmethod
    async def get_all(session: AsyncSession | Session) -> list[StorefrontFolderDTO]:
        """Return all storefront folders ordered by sort_order."""
        stmt = select(StorefrontFolder).order_by(StorefrontFolder.sort_order.asc(), StorefrontFolder.id.asc())
        rows = await session_execute(stmt, session)
        return [StorefrontFolderDTO.model_validate(f, from_attributes=True) for f in rows.scalars().all()]

    @staticmethod
    async def get_all_visible(session: AsyncSession | Session) -> list[StorefrontFolderDTO]:
        """Return all non-hidden storefront folders ordered by sort_order."""
        stmt = (
            select(StorefrontFolder)
            .where(StorefrontFolder.hidden == False)  # noqa: E712
            .order_by(StorefrontFolder.sort_order.asc(), StorefrontFolder.id.asc())
        )
        rows = await session_execute(stmt, session)
        return [StorefrontFolderDTO.model_validate(f, from_attributes=True) for f in rows.scalars().all()]

    @staticmethod
    async def get_by_key(key: str, session: AsyncSession | Session) -> StorefrontFolderDTO | None:
        stmt = select(StorefrontFolder).where(StorefrontFolder.key == key)
        row = await session_execute(stmt, session)
        obj = row.scalar_one_or_none()
        if obj is None:
            return None
        return StorefrontFolderDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def get_by_id(folder_id: int, session: AsyncSession | Session) -> StorefrontFolderDTO | None:
        stmt = select(StorefrontFolder).where(StorefrontFolder.id == folder_id)
        row = await session_execute(stmt, session)
        obj = row.scalar_one_or_none()
        if obj is None:
            return None
        return StorefrontFolderDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def count(session: AsyncSession | Session) -> int:
        stmt = select(func.count(StorefrontFolder.id))
        res = await session_execute(stmt, session)
        return res.scalar_one()

    @staticmethod
    async def create(dto: StorefrontFolderDTO, session: AsyncSession | Session) -> StorefrontFolderDTO:
        obj = StorefrontFolder(**dto.model_dump(exclude={"id"}, exclude_none=True))
        session.add(obj)
        await session_flush(session)
        return StorefrontFolderDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def update(dto: StorefrontFolderDTO, session: AsyncSession | Session) -> None:
        if not dto.id:
            return
        data = dto.model_dump(exclude_none=True)
        stmt = update(StorefrontFolder).where(StorefrontFolder.id == dto.id).values(**data)
        await session_execute(stmt, session)

    @staticmethod
    async def delete_by_id(folder_id: int, session: AsyncSession | Session) -> None:
        stmt = delete(StorefrontFolder).where(StorefrontFolder.id == folder_id)
        await session_execute(stmt, session)
