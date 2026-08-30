from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.batstore_product import BatStoreProduct, BatStoreProductDTO


class BatStoreProductRepository:

    @staticmethod
    async def get_by_product_id(product_id: int, session: AsyncSession | Session) -> BatStoreProductDTO | None:
        stmt = select(BatStoreProduct).where(BatStoreProduct.product_id == product_id)
        row = await session_execute(stmt, session)
        obj = row.scalar_one_or_none()
        if obj is None:
            return None
        return BatStoreProductDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def get_all(session: AsyncSession | Session) -> list[BatStoreProductDTO]:
        stmt = select(BatStoreProduct).order_by(BatStoreProduct.name.asc())
        rows = await session_execute(stmt, session)
        return [BatStoreProductDTO.model_validate(o, from_attributes=True) for o in rows.scalars().all()]

    @staticmethod
    async def get_visible(session: AsyncSession | Session) -> list[BatStoreProductDTO]:
        stmt = (select(BatStoreProduct)
                .where(BatStoreProduct.hidden == False)  # noqa: E712
                .order_by(BatStoreProduct.name.asc()))
        rows = await session_execute(stmt, session)
        return [BatStoreProductDTO.model_validate(o, from_attributes=True) for o in rows.scalars().all()]

    @staticmethod
    async def get_categories(session: AsyncSession | Session) -> list[str]:
        """Return distinct non-null category labels, sorted alphabetically."""
        stmt = (select(BatStoreProduct.category)
                .where(BatStoreProduct.hidden == False, BatStoreProduct.category.isnot(None))  # noqa: E712
                .distinct()
                .order_by(BatStoreProduct.category.asc()))
        rows = await session_execute(stmt, session)
        return [r for r in rows.scalars().all() if r]

    @staticmethod
    async def get_by_category(category: str, session: AsyncSession | Session) -> list[BatStoreProductDTO]:
        """Return visible products in a given category, sorted by name."""
        stmt = (select(BatStoreProduct)
                .where(BatStoreProduct.hidden == False, BatStoreProduct.category == category)  # noqa: E712
                .order_by(BatStoreProduct.name.asc()))
        rows = await session_execute(stmt, session)
        return [BatStoreProductDTO.model_validate(o, from_attributes=True) for o in rows.scalars().all()]

    @staticmethod
    async def get_category_product_count(category: str, session: AsyncSession | Session) -> int:
        """Count visible products in a category."""
        stmt = (select(func.count())
                .select_from(BatStoreProduct)
                .where(BatStoreProduct.hidden == False, BatStoreProduct.category == category))  # noqa: E712
        rows = await session_execute(stmt, session)
        return rows.scalar_one()

    @staticmethod
    async def create(dto: BatStoreProductDTO, session: AsyncSession | Session) -> BatStoreProductDTO:
        obj = BatStoreProduct(**dto.model_dump(exclude_none=True))
        session.add(obj)
        await session_flush(session)
        return BatStoreProductDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def update(dto: BatStoreProductDTO, session: AsyncSession | Session) -> None:
        dto_dict = dto.model_dump()
        none_keys = [k for k, v in dto_dict.items() if v is None]
        for k in none_keys:
            dto_dict.pop(k)
        if "id" not in dto_dict:
            return
        stmt = update(BatStoreProduct).where(BatStoreProduct.product_id == dto.product_id).values(**dto_dict)
        await session_execute(stmt, session)

    @staticmethod
    async def delete_by_product_id(product_id: int, session: AsyncSession | Session) -> None:
        stmt = delete(BatStoreProduct).where(BatStoreProduct.product_id == product_id)
        await session_execute(stmt, session)

    @staticmethod
    async def delete_absent(product_ids: list[int], session: AsyncSession | Session) -> None:
        """Delete local rows whose product is no longer returned by the reseller."""
        if not product_ids:
            return
        stmt = delete(BatStoreProduct).where(BatStoreProduct.product_id.not_in(product_ids))
        await session_execute(stmt, session)
