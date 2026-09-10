import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.order import Order, OrderDTO, BatStoreOrder, BatStoreOrderDTO


class OrderRepository:
    """Universal repository for digital product orders across all suppliers."""

    @staticmethod
    async def create(dto: OrderDTO, session: AsyncSession | Session) -> Order:
        order = Order(
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
                                 limit: int = 20) -> list[Order]:
        stmt = (select(Order)
                .where(Order.telegram_id == telegram_id)
                .order_by(Order.created_at.desc())
                .limit(limit))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_pending(session: AsyncSession | Session) -> list[Order]:
        stmt = (select(Order)
                .where(Order.status == "pending_fulfillment")
                .where(Order.external_order_ref.isnot(None))
                .order_by(Order.created_at.asc()))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(order_id: int, new_status: str,
                            delivery_goods: list | None,
                            session: AsyncSession | Session) -> Order | None:
        stmt = select(Order).where(Order.id == order_id)
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
    async def get_by_id(order_id: int, session: AsyncSession | Session) -> Order | None:
        stmt = select(Order).where(Order.id == order_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_warranty_claimed(order_id: int, claimed: bool, session: AsyncSession | Session) -> Order | None:
        stmt = select(Order).where(Order.id == order_id)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if order:
            order.warranty_claimed = claimed
            order.warranty_claimed_at = datetime.datetime.now(datetime.timezone.utc)
            await session.flush()
        return order

    @staticmethod
    async def update(order: Order, session: AsyncSession | Session) -> Order:
        session.add(order)
        await session.flush()
        return order


# Backward-compatibility alias
BatStoreOrderRepository = OrderRepository
