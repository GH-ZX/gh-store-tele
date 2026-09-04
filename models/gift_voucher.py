import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey

from models.base import Base


class GiftVoucher(Base):
    """Prepaid digital gift voucher code that credits user balance upon redemption."""
    __tablename__ = "gift_vouchers"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    amount_usd = Column(Float, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    redeemed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_redeemed = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"GiftVoucher[{self.code}] ${self.amount_usd}"


class GiftVoucherDTO(BaseModel):
    id: int | None = None
    code: str
    amount_usd: float
    created_by_user_id: int | None = None
    redeemed_by_user_id: int | None = None
    is_redeemed: bool = False
    created_at: datetime.datetime | None = None
    redeemed_at: datetime.datetime | None = None


class GiftVoucherAdmin(ModelView, model=GiftVoucher):
    name = "Gift Voucher"
    name_plural = "Gift Vouchers"
    icon = "fa-solid fa-gift"
    category = "Payments"

    column_list = [
        GiftVoucher.id,
        GiftVoucher.code,
        GiftVoucher.amount_usd,
        GiftVoucher.is_redeemed,
        GiftVoucher.redeemed_by_user_id,
        GiftVoucher.created_at,
        GiftVoucher.redeemed_at,
    ]
    column_searchable_list = [GiftVoucher.code]
    column_sortable_list = [GiftVoucher.id, GiftVoucher.amount_usd, GiftVoucher.created_at]
    can_create = True
    can_edit = True
    can_delete = False
    can_export = True
