"""Repository for affiliate referral withdrawal requests."""
import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from db import session_execute, session_flush
from models.referral_withdrawal import ReferralWithdrawal, ReferralWithdrawalDTO


class ReferralWithdrawalRepository:
    @staticmethod
    async def create(dto: ReferralWithdrawalDTO, session: AsyncSession) -> ReferralWithdrawal:
        withdrawal = ReferralWithdrawal(
            telegram_id=dto.telegram_id,
            amount_usd=dto.amount_usd,
            method=dto.method,
            destination_address=dto.destination_address,
            status=dto.status,
            admin_notes=dto.admin_notes,
        )
        session.add(withdrawal)
        await session_flush(session)
        return withdrawal

    @staticmethod
    async def get_by_id(withdrawal_id: int, session: AsyncSession) -> ReferralWithdrawal | None:
        stmt = select(ReferralWithdrawal).where(ReferralWithdrawal.id == withdrawal_id)
        return (await session_execute(stmt, session)).scalar_one_or_none()

    @staticmethod
    async def get_by_telegram_id(telegram_id: int, session: AsyncSession, limit: int = 20) -> list[ReferralWithdrawal]:
        stmt = (
            select(ReferralWithdrawal)
            .where(ReferralWithdrawal.telegram_id == telegram_id)
            .order_by(desc(ReferralWithdrawal.id))
            .limit(limit)
        )
        return list((await session_execute(stmt, session)).scalars().all())

    @staticmethod
    async def get_pending(session: AsyncSession) -> list[ReferralWithdrawal]:
        stmt = (
            select(ReferralWithdrawal)
            .where(ReferralWithdrawal.status == "pending")
            .order_by(desc(ReferralWithdrawal.id))
        )
        return list((await session_execute(stmt, session)).scalars().all())

    @staticmethod
    async def update_status(
        withdrawal_id: int,
        status: str,
        admin_notes: str | None,
        session: AsyncSession
    ) -> ReferralWithdrawal | None:
        row = await ReferralWithdrawalRepository.get_by_id(withdrawal_id, session)
        if row is not None:
            row.status = status
            row.admin_notes = admin_notes
            row.processed_at = datetime.datetime.now(datetime.timezone.utc)
            await session_flush(session)
        return row
