from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.stars_payment import StarsPayment, StarsPaymentDTO


class StarsPaymentRepository:

    @staticmethod
    async def create(dto: StarsPaymentDTO, session: AsyncSession | Session) -> StarsPayment:
        payment = StarsPayment(
            telegram_id=dto.telegram_id,
            telegram_payment_charge_id=dto.telegram_payment_charge_id,
            provider_payment_charge_id=dto.provider_payment_charge_id,
            stars_amount=dto.stars_amount or 0,
            usd_amount=dto.usd_amount or 0.0,
            invoice_payload=dto.invoice_payload,
        )
        session.add(payment)
        await session.flush()
        return payment

    @staticmethod
    async def get_by_charge_id(charge_id: str,
                               session: AsyncSession | Session) -> StarsPayment | None:
        stmt = select(StarsPayment).where(StarsPayment.telegram_payment_charge_id == charge_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_telegram_id(telegram_id: int,
                                 session: AsyncSession | Session) -> list[StarsPayment]:
        stmt = (select(StarsPayment)
                .where(StarsPayment.telegram_id == telegram_id)
                .order_by(StarsPayment.created_at.desc()))
        result = await session.execute(stmt)
        return list(result.scalars().all())
