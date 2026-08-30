from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.sam_payment import SamPayment, SamPaymentDTO


class SamPaymentRepository:

    @staticmethod
    async def create(dto: SamPaymentDTO, session: AsyncSession | Session) -> SamPayment:
        payment = SamPayment(
            invoice_id=dto.invoice_id,
            telegram_id=dto.telegram_id,
            method=dto.method or "shamcash",
            currency=dto.currency or "USD",
            amount=dto.amount or 0.0,
            usd_amount=dto.usd_amount or 0.0,
            payment_url=dto.payment_url,
            event=dto.event,
            transaction_ref=dto.transaction_ref,
        )
        session.add(payment)
        await session.flush()
        return payment

    @staticmethod
    async def get_by_invoice_id(invoice_id: str,
                                session: AsyncSession | Session) -> SamPayment | None:
        stmt = select(SamPayment).where(SamPayment.invoice_id == invoice_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_event(invoice_id: str,
                         event: str,
                         transaction_ref: str | None,
                         session: AsyncSession | Session) -> None:
        stmt = (update(SamPayment)
                .where(SamPayment.invoice_id == invoice_id)
                .values(event=event, transaction_ref=transaction_ref))
        await session.execute(stmt)
        await session.flush()