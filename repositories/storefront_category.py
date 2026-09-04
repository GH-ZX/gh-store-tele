from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.storefront_category import StorefrontCategory, StorefrontCategoryDTO


class StorefrontCategoryRepository:
    @staticmethod
    async def get_all_visible(session: AsyncSession | Session) -> list[StorefrontCategoryDTO]:
        """Return all visible storefront categories ordered by sort_order."""
        stmt = (
            select(StorefrontCategory)
            .where(StorefrontCategory.hidden == False)  # noqa: E712
            .order_by(StorefrontCategory.sort_order.asc(), StorefrontCategory.id.asc())
        )
        rows = await session_execute(stmt, session)
        return [StorefrontCategoryDTO.model_validate(c, from_attributes=True) for c in rows.scalars().all()]

    @staticmethod
    async def get_by_name(name: str, session: AsyncSession | Session) -> StorefrontCategoryDTO | None:
        stmt = select(StorefrontCategory).where(StorefrontCategory.name == name)
        row = await session_execute(stmt, session)
        obj = row.scalar_one_or_none()
        if obj is None:
            return None
        return StorefrontCategoryDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def count(session: AsyncSession | Session) -> int:
        stmt = select(func.count(StorefrontCategory.id))
        res = await session_execute(stmt, session)
        return res.scalar_one()

    @staticmethod
    async def create(dto: StorefrontCategoryDTO, session: AsyncSession | Session) -> StorefrontCategoryDTO:
        obj = StorefrontCategory(**dto.model_dump(exclude={"id"}, exclude_none=True))
        session.add(obj)
        await session_flush(session)
        return StorefrontCategoryDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def update(dto: StorefrontCategoryDTO, session: AsyncSession | Session) -> None:
        if not dto.id:
            return
        data = dto.model_dump(exclude_none=True)
        stmt = update(StorefrontCategory).where(StorefrontCategory.id == dto.id).values(**data)
        await session_execute(stmt, session)
