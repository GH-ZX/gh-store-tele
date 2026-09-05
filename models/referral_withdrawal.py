"""Model for affiliate referral commission withdrawal requests."""
import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, BigInteger, Float, Text, DateTime
from models.base import Base


class ReferralWithdrawal(Base):
    __tablename__ = "referral_withdrawals"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    amount_usd = Column(Float, nullable=False)
    method = Column(Text, nullable=False)  # 'usdt_bep20' | 'shamcash'
    destination_address = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")  # 'pending' | 'approved' | 'rejected'
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    admin_notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"ReferralWithdrawal #{self.id} tg:{self.telegram_id} ${self.amount_usd}"


class ReferralWithdrawalDTO(BaseModel):
    id: int | None = None
    telegram_id: int
    amount_usd: float
    method: str
    destination_address: str
    status: str = "pending"
    created_at: datetime.datetime | None = None
    processed_at: datetime.datetime | None = None
    admin_notes: str | None = None


class ReferralWithdrawalAdmin(ModelView, model=ReferralWithdrawal):
    name = "Referral Withdrawal"
    name_plural = "Referral Withdrawals"
    icon = "fa-solid fa-money-bill-transfer"
    category = "Financials"
    column_list = [
        ReferralWithdrawal.id,
        ReferralWithdrawal.telegram_id,
        ReferralWithdrawal.amount_usd,
        ReferralWithdrawal.method,
        ReferralWithdrawal.destination_address,
        ReferralWithdrawal.status,
        ReferralWithdrawal.created_at,
    ]
    can_create = False
    can_edit = True
    can_delete = False
