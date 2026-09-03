from datetime import datetime, timezone
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.restock_subscription import RestockSubscription, RestockSubscriptionDTO


class RestockSubscriptionRepository:

    @staticmethod
    async def subscribe(
        telegram_id: int,
        user_id: int | None,
        batstore_product_id: int | None,
        subcategory_id: int | None,
        language: str,
        session: AsyncSession | Session
    ) -> tuple[RestockSubscriptionDTO, bool]:
        """Subscribe a user for restock notifications. Returns (dto, was_created)."""
        stmt = select(RestockSubscription).where(
            RestockSubscription.telegram_id == telegram_id,
            RestockSubscription.batstore_product_id == batstore_product_id if batstore_product_id is not None else RestockSubscription.batstore_product_id.is_(None),
            RestockSubscription.subcategory_id == subcategory_id if subcategory_id is not None else RestockSubscription.subcategory_id.is_(None),
        )
        res = await session_execute(stmt, session)
        existing = res.scalar_one_or_none()

        if existing:
            # Re-activate subscription if it was already notified
            existing.notified_at = None
            existing.language = language
            if user_id and not existing.user_id:
                existing.user_id = user_id
            await session_flush(session)
            return RestockSubscriptionDTO.model_validate(existing, from_attributes=True), False

        obj = RestockSubscription(
            telegram_id=telegram_id,
            user_id=user_id,
            batstore_product_id=batstore_product_id,
            subcategory_id=subcategory_id,
            language=language,
            notified_at=None,
        )
        if hasattr(session, "add"):
            session.add(obj)
        await session_flush(session)
        return RestockSubscriptionDTO.model_validate(obj, from_attributes=True), True

    @staticmethod
    async def unsubscribe(
        telegram_id: int,
        batstore_product_id: int | None,
        subcategory_id: int | None,
        session: AsyncSession | Session
    ) -> bool:
        """Unsubscribe a user from restock notifications. Returns True if removed."""
        stmt = delete(RestockSubscription).where(
            RestockSubscription.telegram_id == telegram_id,
            RestockSubscription.batstore_product_id == batstore_product_id if batstore_product_id is not None else RestockSubscription.batstore_product_id.is_(None),
            RestockSubscription.subcategory_id == subcategory_id if subcategory_id is not None else RestockSubscription.subcategory_id.is_(None),
        )
        res = await session_execute(stmt, session)
        await session_flush(session)
        return getattr(res, "rowcount", 1) > 0

    @staticmethod
    async def is_subscribed(
        telegram_id: int,
        batstore_product_id: int | None,
        subcategory_id: int | None,
        session: AsyncSession | Session
    ) -> bool:
        """Check if user has an active (unnotified) subscription."""
        stmt = select(RestockSubscription).where(
            RestockSubscription.telegram_id == telegram_id,
            RestockSubscription.batstore_product_id == batstore_product_id if batstore_product_id is not None else RestockSubscription.batstore_product_id.is_(None),
            RestockSubscription.subcategory_id == subcategory_id if subcategory_id is not None else RestockSubscription.subcategory_id.is_(None),
            RestockSubscription.notified_at.is_(None),
        )
        res = await session_execute(stmt, session)
        return res.scalar_one_or_none() is not None

    @staticmethod
    async def get_active_subscribers_for_product(
        batstore_product_id: int,
        session: AsyncSession | Session
    ) -> list[RestockSubscriptionDTO]:
        """Fetch all pending subscribers waiting for a BatStore product restock."""
        stmt = select(RestockSubscription).where(
            RestockSubscription.batstore_product_id == batstore_product_id,
            RestockSubscription.notified_at.is_(None),
        )
        res = await session_execute(stmt, session)
        return [RestockSubscriptionDTO.model_validate(o, from_attributes=True) for o in res.scalars().all()]

    @staticmethod
    async def get_active_subscribers_for_subcategory(
        subcategory_id: int,
        session: AsyncSession | Session
    ) -> list[RestockSubscriptionDTO]:
        """Fetch all pending subscribers waiting for a native subcategory restock."""
        stmt = select(RestockSubscription).where(
            RestockSubscription.subcategory_id == subcategory_id,
            RestockSubscription.notified_at.is_(None),
        )
        res = await session_execute(stmt, session)
        return [RestockSubscriptionDTO.model_validate(o, from_attributes=True) for o in res.scalars().all()]

    @staticmethod
    async def mark_notified(
        subscription_ids: list[int],
        session: AsyncSession | Session
    ) -> None:
        """Mark subscriptions as notified."""
        if not subscription_ids:
            return
        now = datetime.now(timezone.utc)
        stmt = (
            update(RestockSubscription)
            .where(RestockSubscription.id.in_(subscription_ids))
            .values(notified_at=now)
        )
        await session_execute(stmt, session)
        await session_flush(session)
