from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.batstore_product import BatStoreProduct, BatStoreProductDTO


class BatStoreProductRepository:
    _redis = None

    @classmethod
    def set_redis(cls, redis_client) -> None:
        cls._redis = redis_client

    @classmethod
    async def invalidate_cache(cls) -> None:
        if cls._redis is not None:
            try:
                await cls._redis.delete("ghstore:cache:batstore_cats")
            except Exception:
                pass

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
    async def find_alternate_in_stock(
        name_or_clean: str,
        target_supplier: str,
        session: AsyncSession | Session
    ) -> BatStoreProductDTO | None:
        """Find an in-stock equivalent product from an alternate supplier for auto-failover."""
        clean = (name_or_clean or "").strip().lower()
        if not clean:
            return None
        stmt = (
            select(BatStoreProduct)
            .where(
                BatStoreProduct.supplier == target_supplier,
                BatStoreProduct.hidden == False,
                or_(BatStoreProduct.stock == None, BatStoreProduct.stock > 0)
            )
        )
        rows = (await session_execute(stmt, session)).scalars().all()
        for p in rows:
            p_name = (p.custom_name or p.name or "").lower()
            if clean in p_name or p_name in clean:
                return BatStoreProductDTO.model_validate(p, from_attributes=True)
        return None

    @classmethod
    async def get_categories(cls, session: AsyncSession | Session) -> list[str]:
        """Return distinct non-null category labels, sorted alphabetically (cached in Redis)."""
        if cls._redis is not None:
            try:
                cached = await cls._redis.get("ghstore:cache:batstore_cats")
                if cached:
                    import json
                    return json.loads(cached)
            except Exception:
                pass

        stmt = (select(BatStoreProduct.category)
                .where(BatStoreProduct.hidden == False, BatStoreProduct.category.isnot(None))  # noqa: E712
                .distinct()
                .order_by(BatStoreProduct.category.asc()))
        rows = await session_execute(stmt, session)
        cats = [r for r in rows.scalars().all() if r]

        if cls._redis is not None and cats:
            try:
                import json
                await cls._redis.setex("ghstore:cache:batstore_cats", 1800, json.dumps(cats))
            except Exception:
                pass
        return cats
    @staticmethod
    async def get_by_category(category: str, session: AsyncSession | Session) -> list[BatStoreProductDTO]:
        """Return visible products in a given category, sorted by name."""
        stmt = (select(BatStoreProduct)
                .where(BatStoreProduct.hidden == False, BatStoreProduct.category == category)  # noqa: E712
                .order_by(BatStoreProduct.name.asc()))
        rows = await session_execute(stmt, session)
        return [BatStoreProductDTO.model_validate(o, from_attributes=True) for o in rows.scalars().all()]

    @staticmethod
    async def search(query: str, session: AsyncSession | Session, limit: int = 15) -> list[BatStoreProductDTO]:
        """Search products by name or description (case-insensitive)."""
        pattern = f"%{query.strip()}%"
        stmt = (
            select(BatStoreProduct)
            .where(
                BatStoreProduct.hidden == False,  # noqa: E712
                or_(
                    BatStoreProduct.name.ilike(pattern),
                    BatStoreProduct.description.ilike(pattern),
                    BatStoreProduct.category.ilike(pattern),
                )
            )
            .order_by(BatStoreProduct.name.asc())
            .limit(limit)
        )
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
        await BatStoreProductRepository.invalidate_cache()
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
        await BatStoreProductRepository.invalidate_cache()
        stmt = update(BatStoreProduct).where(BatStoreProduct.product_id == dto.product_id).values(**dto_dict)
        await session_execute(stmt, session)

    @staticmethod
    async def delete_by_product_id(product_id: int, session: AsyncSession | Session) -> None:
        stmt = delete(BatStoreProduct).where(BatStoreProduct.product_id == product_id)
        await BatStoreProductRepository.invalidate_cache()
        await session_execute(stmt, session)

    @staticmethod
    async def delete_absent(product_ids: list[int], session: AsyncSession | Session) -> None:
        """Delete local rows whose product is no longer returned by the reseller."""
        if not product_ids:
            return
        stmt = delete(BatStoreProduct).where(BatStoreProduct.product_id.not_in(product_ids))
        await BatStoreProductRepository.invalidate_cache()
        await session_execute(stmt, session)
