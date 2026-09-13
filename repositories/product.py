import logging
from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.product import Product, ProductDTO, BatStoreProduct, BatStoreProductDTO


def supplier_owns_row(existing, expected_supplier: str, local_id: int) -> bool:
    """Guard against cross-supplier product_id collisions during catalog sync.

    Every supplier writes into the same global (unique) product_id namespace.
    Returns True when the existing row belongs to the syncing supplier (or has no
    supplier tag yet, i.e. a legacy BatStore row). Otherwise warns and returns False
    so the sync skips the row instead of silently overwriting another supplier's
    product.
    """
    actual = (getattr(existing, "supplier", None) or "batstore").strip().lower()
    expected = (expected_supplier or "batstore").strip().lower()
    if actual == expected:
        return True
    logging.warning(
        "Supplier collision: %s sync wants product_id=%s but the row belongs to supplier '%s'; "
        "skipping to preserve data.",
        expected, local_id, actual,
    )
    return False


class ProductRepository:
    """Universal repository for digital products across all upstream suppliers."""
    _redis = None

    @classmethod
    def set_redis(cls, redis_client) -> None:
        cls._redis = redis_client

    @classmethod
    async def invalidate_cache(cls) -> None:
        if cls._redis is not None:
            try:
                await cls._redis.delete("ghstore:cache:batstore_cats")
                await cls._redis.delete("ghstore:cache:reseller_products")
            except Exception as e:
                logging.debug("Failed to invalidate product cache: %s", e)

    @staticmethod
    async def get_by_product_id(product_id: int, session: AsyncSession | Session) -> ProductDTO | None:
        stmt = select(Product).where(Product.product_id == product_id)
        row = await session_execute(stmt, session)
        obj = row.scalar_one_or_none()
        if obj is None:
            return None
        return ProductDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def get_all(session: AsyncSession | Session) -> list[ProductDTO]:
        stmt = select(Product).order_by(Product.name.asc())
        rows = await session_execute(stmt, session)
        return [ProductDTO.model_validate(o, from_attributes=True) for o in rows.scalars().all()]

    @staticmethod
    async def get_visible(session: AsyncSession | Session) -> list[ProductDTO]:
        stmt = (select(Product)
                .where(Product.hidden == False)  # noqa: E712
                .order_by(Product.name.asc()))
        rows = await session_execute(stmt, session)
        return [ProductDTO.model_validate(o, from_attributes=True) for o in rows.scalars().all()]

    _MIN_MATCH_SCORE = 0.5

    @staticmethod
    def match_tokens(value: str | None) -> frozenset[str]:
        """Tokenize a product name into a deterministic lowercase token set."""
        import re

        s = str(value or "").strip().lower()
        s = s.replace("+", " plus ")
        s = re.sub(r"[^a-z0-9\s]+", " ", s)
        return frozenset(s.split())

    @staticmethod
    def token_overlap(a: frozenset[str], b: frozenset[str]) -> float:
        """Ratio of shared tokens over the larger token set (0.0 .. 1.0)."""
        if not a or not b:
            return 0.0
        return len(a & b) / max(len(a), len(b))

    @staticmethod
    async def find_approved_equivalent(
        product_id: int | None,
        session: AsyncSession | Session,
    ) -> int | None:
        """Return the other side of an admin-approved equivalence pair, if any.

        Pairs are bidirectional by convention, so looking up either (A -> B) or
        (B -> A) resolves to the opposing ``product_id``.
        """
        if not product_id:
            return None
        from models.approved_equivalent import ApprovedEquivalent

        stmt = (
            select(ApprovedEquivalent)
            .where(
                or_(
                    ApprovedEquivalent.product_id == product_id,
                    ApprovedEquivalent.equivalent_product_id == product_id,
                )
            )
            .limit(10)
        )
        rows = (await session_execute(stmt, session)).scalars().all()
        for row in rows:
            if row.product_id == product_id:
                return int(row.equivalent_product_id)
            if row.equivalent_product_id == product_id:
                return int(row.product_id)
        return None

    @staticmethod
    async def find_alternate_in_stock(
        name_or_clean: str,
        target_supplier: str,
        session: AsyncSession | Session,
        product_id: int | None = None,
    ) -> ProductDTO | None:
        """Find an in-stock equivalent product from an alternate supplier.

        Resolution order:
        1. Admin-approved pair (``approved_equivalents``) for ``product_id``.
        2. Deterministic normalized-token match against visible in-stock rows of
           ``target_supplier`` (token overlap >= ``_MIN_MATCH_SCORE``, ties broken
           by smallest ``product_id``).

        Never routes to a hidden or out-of-stock row, and never returns the
        primary row itself.
        """
        if product_id is not None:
            approved = await ProductRepository.find_approved_equivalent(product_id, session)
            if approved is not None and approved != product_id:
                candidate = await ProductRepository.get_by_product_id(approved, session)
                if (
                    candidate is not None
                    and candidate.supplier == target_supplier
                    and not candidate.hidden
                    and (candidate.stock is None or candidate.stock > 0)
                ):
                    return candidate

        source_tokens = ProductRepository.match_tokens(name_or_clean)
        if not source_tokens:
            return None
        stmt = (
            select(Product)
            .where(
                Product.supplier == target_supplier,
                Product.hidden == False,
                or_(Product.stock == None, Product.stock > 0),
            )
        )
        rows = (await session_execute(stmt, session)).scalars().all()
        best = None
        best_score = -1.0
        for p in rows:
            if product_id is not None and p.product_id == product_id:
                continue
            p_tokens = ProductRepository.match_tokens(p.custom_name or p.name or "")
            if not p_tokens:
                continue
            score = ProductRepository.token_overlap(source_tokens, p_tokens)
            if score > best_score:
                best, best_score = p, score
            elif (
                score == best_score
                and best is not None
                and (best.product_id or 0) > (p.product_id or 0)
            ):
                best = p
        if best is None or best_score < ProductRepository._MIN_MATCH_SCORE:
            return None
        return ProductDTO.model_validate(best, from_attributes=True)

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

        stmt = (select(Product.category)
                .where(Product.hidden == False, Product.category.isnot(None))  # noqa: E712
                .distinct()
                .order_by(Product.category.asc()))
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
    async def get_by_category(category: str, session: AsyncSession | Session) -> list[ProductDTO]:
        """Return visible products in a given category, sorted by name."""
        stmt = (select(Product)
                .where(Product.hidden == False, Product.category == category)  # noqa: E712
                .order_by(Product.name.asc()))
        rows = await session_execute(stmt, session)
        return [ProductDTO.model_validate(o, from_attributes=True) for o in rows.scalars().all()]

    @staticmethod
    async def search(query: str, session: AsyncSession | Session, limit: int = 15) -> list[ProductDTO]:
        """Search products by name or description (case-insensitive)."""
        pattern = f"%{query.strip()}%"
        stmt = (
            select(Product)
            .where(
                Product.hidden == False,  # noqa: E712
                or_(
                    Product.name.ilike(pattern),
                    Product.description.ilike(pattern),
                    Product.category.ilike(pattern),
                )
            )
            .order_by(Product.name.asc())
            .limit(limit)
        )
        rows = await session_execute(stmt, session)
        return [ProductDTO.model_validate(o, from_attributes=True) for o in rows.scalars().all()]

    @staticmethod
    async def get_category_product_count(category: str, session: AsyncSession | Session) -> int:
        """Count visible products in a category."""
        stmt = (select(func.count())
                .select_from(Product)
                .where(Product.hidden == False, Product.category == category))  # noqa: E712
        rows = await session_execute(stmt, session)
        return rows.scalar_one()

    @staticmethod
    async def create(dto: ProductDTO, session: AsyncSession | Session) -> ProductDTO:
        obj = Product(**dto.model_dump(exclude_none=True))
        session.add(obj)
        await ProductRepository.invalidate_cache()
        await session_flush(session)
        return ProductDTO.model_validate(obj, from_attributes=True)

    @staticmethod
    async def update(dto: ProductDTO, session: AsyncSession | Session) -> None:
        dto_dict = dto.model_dump()
        none_keys = [k for k, v in dto_dict.items() if v is None]
        for k in none_keys:
            dto_dict.pop(k)
        if "hidden_reason" in getattr(dto, "model_fields", {}):
            dto_dict["hidden_reason"] = dto.hidden_reason
        if "id" not in dto_dict and "product_id" not in dto_dict:
            return
        await ProductRepository.invalidate_cache()
        stmt = update(Product).where(Product.product_id == dto.product_id).values(**dto_dict)
        await session_execute(stmt, session)

    @staticmethod
    async def delete_by_product_id(product_id: int, session: AsyncSession | Session) -> None:
        stmt = delete(Product).where(Product.product_id == product_id)
        await ProductRepository.invalidate_cache()
        await session_execute(stmt, session)

    @staticmethod
    async def delete_absent(product_ids: list[int], session: AsyncSession | Session, supplier: str = "batstore") -> None:
        """Delete local rows whose product is no longer returned by the reseller for a specific supplier."""
        if not product_ids:
            return
        stmt = delete(Product).where(
            Product.supplier == supplier,
            Product.product_id.not_in(product_ids)
        )
        await ProductRepository.invalidate_cache()
        await session_execute(stmt, session)

    @staticmethod
    async def set_reseller_pricing(
        product_id: int,
        reseller_price_usd: float | None,
        reseller_margin_pct: float | None,
        session: AsyncSession | Session
    ) -> None:
        """Set custom reseller pricing for a specific product."""
        stmt = (
            update(Product)
            .where(Product.product_id == product_id)
            .values(
                reseller_price_usd=reseller_price_usd,
                reseller_margin_pct=reseller_margin_pct
            )
        )
        await ProductRepository.invalidate_cache()
        await session_execute(stmt, session)


# Backward-compatibility alias
BatStoreProductRepository = ProductRepository
