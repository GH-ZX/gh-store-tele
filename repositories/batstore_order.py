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
