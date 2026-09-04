import datetime
import secrets
import string
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.gift_voucher import GiftVoucher, GiftVoucherDTO
from models.user import User


class GiftVoucherRepository:

    @staticmethod
    def generate_code(prefix: str = "GH") -> str:
        """Generate a clean, uppercase 12-char voucher code like GH-7X2M-9P4K."""
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # exclude ambiguous chars O/0, I/1
        part1 = "".join(secrets.choice(alphabet) for _ in range(4))
        part2 = "".join(secrets.choice(alphabet) for _ in range(4))
        return f"{prefix}-{part1}-{part2}"

    @staticmethod
    async def create(dto: GiftVoucherDTO, session: AsyncSession | Session) -> GiftVoucher:
        voucher = GiftVoucher(
            code=dto.code.strip().upper(),
            amount_usd=round(float(dto.amount_usd), 2),
            created_by_user_id=dto.created_by_user_id,
            is_redeemed=False,
        )
        session.add(voucher)
        await session_flush(session)
        return voucher

    @staticmethod
    async def get_by_code(code: str, session: AsyncSession | Session) -> GiftVoucher | None:
        clean = code.strip().upper()
        stmt = select(GiftVoucher).where(GiftVoucher.code == clean)
        res = await session_execute(stmt, session)
        return res.scalar_one_or_none()

    @staticmethod
    async def redeem(code: str, user_id: int, session: AsyncSession | Session) -> tuple[bool, float, str]:
        """Atomically redeem a gift voucher code.

        Returns (success, amount_credited, message).
        """
        clean = code.strip().upper()
        # 1. Atomically mark voucher as redeemed
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = (
            update(GiftVoucher)
            .where(GiftVoucher.code == clean, GiftVoucher.is_redeemed == False)
            .values(is_redeemed=True, redeemed_by_user_id=user_id, redeemed_at=now)
            .returning(GiftVoucher.id, GiftVoucher.amount_usd)
        )
        res = await session_execute(stmt, session)
        row = res.first()
        if not row:
            # Check if already redeemed
            existing = await GiftVoucherRepository.get_by_code(clean, session)
            if existing and existing.is_redeemed:
                return False, 0.0, "voucher_already_redeemed"
            return False, 0.0, "voucher_not_found"

        voucher_id, amount = row
        amount = float(amount)

        # 2. Credit user balance
        stmt_user = (
            update(User)
            .where(User.id == user_id)
            .values(top_up_amount=func.coalesce(User.top_up_amount, 0.0) + amount)
        )
        await session_execute(stmt_user, session)
        return True, amount, "voucher_redeemed_successfully"
