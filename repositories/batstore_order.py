from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.batstore_order import BatStoreOrder, BatStoreOrderDTO


class BatStoreOrderRepository:

    @staticmethod
    async def create(dto: BatStoreOrderDTO, session: AsyncSession | Session) -> BatStoreOrder:
        order = BatStoreOrder(
            telegram_id=dto.telegram_id,
            total_sell=dto.total_sell or 0.0,
            status=dto.status or "completed",
            external_order_ref=dto.external_order_ref,
            customer_reference=dto.customer_reference,
            details=dto.details,
        )
        session.add(order)
        await session.flush()
        return order

    @staticmethod
    async def get_by_telegram_id(telegram_id: int,
                                 session: AsyncSession | Session,
                                 limit: int = 20) -> list[BatStoreOrder]:
        stmt = (select(BatStoreOrder)
                .where(BatStoreOrder.telegram_id == telegram_id)
                .order_by(BatStoreOrder.created_at.desc())
                .limit(limit))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_pending(session: AsyncSession | Session) -> list[BatStoreOrder]:
        stmt = (select(BatStoreOrder)
                .where(BatStoreOrder.status == "pending_fulfillment")
                .where(BatStoreOrder.external_order_ref.isnot(None))
                .order_by(BatStoreOrder.created_at.asc()))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(order_id: int, new_status: str,
                            delivery_goods: list | None,
                            session: AsyncSession | Session) -> BatStoreOrder | None:
        stmt = select(BatStoreOrder).where(BatStoreOrder.id == order_id)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None:
            return None
        order.status = new_status
        if delivery_goods and order.details:
            for detail in order.details:
                if "delivery_goods" not in detail:
                    detail["delivery_goods"] = delivery_goods
        elif delivery_goods and not order.details:
            order.details = [{"delivery_goods": delivery_goods}]
        await session.flush()
        return order

    @staticmethod
    async def get_by_id(order_id: int, session: AsyncSession | Session) -> BatStoreOrder | None:
        stmt = select(BatStoreOrder).where(BatStoreOrder.id == order_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_warranty_claimed(order_id: int, claimed: bool, session: AsyncSession | Session) -> None:
        import datetime
        stmt = select(BatStoreOrder).where(BatStoreOrder.id == order_id)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if order:
            order.warranty_claimed = claimed
            order.warranty_claimed_at = datetime.datetime.now(datetime.timezone.utc)
            await session.flush()
        return order
