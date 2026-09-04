import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, BigInteger, Float, Text, DateTime

from models.base import Base


class StarsPayment(Base):
    """Persists Telegram Stars top-ups for customer balance.

    Stores telegram_payment_charge_id with a unique index for idempotency
    against webhook retries.
    """
    __tablename__ = "stars_payments"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    telegram_payment_charge_id = Column(Text, nullable=False, unique=True, index=True)
    provider_payment_charge_id = Column(Text, nullable=True)
    stars_amount = Column(Integer, nullable=False, default=0)
    usd_amount = Column(Float, nullable=False, default=0.0)
    invoice_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    def __repr__(self):
        return f"StarsPayment charge_id={self.telegram_payment_charge_id} user={self.telegram_id}"


class StarsPaymentDTO(BaseModel):
    id: int | None = None
    telegram_id: int | None = None
    telegram_payment_charge_id: str | None = None
    provider_payment_charge_id: str | None = None
    stars_amount: int | None = 0
    usd_amount: float | None = 0.0
    invoice_payload: str | None = None
    created_at: datetime.datetime | None = None


class StarsPaymentAdmin(ModelView, model=StarsPayment):
    name = "Stars Payment"
    name_plural = "Stars Payments"
    icon = "fa-solid fa-star"
    category = "Payments"

    column_list = [
        StarsPayment.id,
        StarsPayment.telegram_id,
        StarsPayment.telegram_payment_charge_id,
        StarsPayment.stars_amount,
        StarsPayment.usd_amount,
        StarsPayment.created_at,
    ]
    column_labels = {
        StarsPayment.id: "ID",
        StarsPayment.telegram_id: "Telegram ID",
        StarsPayment.telegram_payment_charge_id: "Charge ID",
        StarsPayment.stars_amount: "Stars",
        StarsPayment.usd_amount: "USD",
        StarsPayment.created_at: "Created",
    }
    can_create = False
    can_edit = False
    can_delete = False
