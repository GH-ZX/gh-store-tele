from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db import session_flush, session_execute
from models.referral import ReferralBonusDTO, ReferralBonus


class ReferralRepository:
    @staticmethod
    async def create(referral_bonus_dto: ReferralBonusDTO, session: AsyncSession) -> ReferralBonusDTO:
        referral_bonus = ReferralBonus(**referral_bonus_dto.model_dump(exclude={"referral_user_dto",
                                                                                "referrer_user_dto"}))
        session.add(referral_bonus)
        await session_flush(session)
        referral_bonus_dto.id = referral_bonus.id
        return referral_bonus_dto

    @staticmethod
    async def get_bonus_sum_as_referral(referral_user_id: int, session: AsyncSession):
        stmt = (
            select(
                func.coalesce(
                    func.sum(ReferralBonus.applied_referral_bonus),
                    0
                )
            )
            .where(ReferralBonus.referral_user_id == referral_user_id)
        )
        result = await session_execute(stmt, session)
        return result.scalar_one()

    @staticmethod
    async def get_bonus_sum_as_referrer(referrer_user_id: int, session: AsyncSession):
        stmt = (
            select(
                func.coalesce(
                    func.sum(ReferralBonus.applied_referrer_bonus),
                    0
                )
            )
            .where(ReferralBonus.referrer_user_id == referrer_user_id)
        )
        result = await session_execute(stmt, session)
        return result.scalar_one()

    @staticmethod
    async def get_referrals_breakdown(referrer_user_id: int, session: AsyncSession) -> list[dict]:
        from models.user import User
        stmt = (
            select(
                User.id,
                User.telegram_username,
                User.telegram_id,
                User.registered_at,
                func.coalesce(func.sum(ReferralBonus.applied_referrer_bonus), 0.0).label("earned_from_user"),
                func.count(ReferralBonus.id).label("orders_count")
            )
            .outerjoin(ReferralBonus, (ReferralBonus.referral_user_id == User.id) & (ReferralBonus.referrer_user_id == referrer_user_id))
            .where(User.referred_by_user_id == referrer_user_id)
            .group_by(User.id, User.telegram_username, User.telegram_id, User.registered_at)
            .order_by(func.coalesce(func.sum(ReferralBonus.applied_referrer_bonus), 0.0).desc())
            .limit(30)
        )
        rows = await session_execute(stmt, session)
        res = []
        for r in rows.all():
            uname = f"@{r.telegram_username}" if r.telegram_username else f"ID: ...{str(r.telegram_id)[-4:]}"
            res.append({
                "user_display": uname,
                "registered_at": r.registered_at.strftime("%b %d, %Y") if r.registered_at else "",
                "earned": round(float(r.earned_from_user), 2),
                "orders_count": int(r.orders_count)
            })
        return res
