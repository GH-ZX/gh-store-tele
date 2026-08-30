import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, BigInteger, Float, Text, DateTime

from models.base import Base


class SamPayment(Base):
    """Persists the mapping invoiceId -> (customer, fiat amount) for SAM top-ups.

    `event` is 'invoice.paid' | 'invoice.expired' | 'pending'.
    """
    __tablename__ = "sam_payments"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Text, nullable=False, unique=True, index=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    method = Column(Text, nullable=False, default="shamcash")
    currency = Column(Text, nullable=False, default="USD")
    amount = Column(Float, nullable=False, default=0.0)
    usd_amount = Column(Float, nullable=False, default=0.0)
    payment_url = Column(Text, nullable=True)
    event = Column(Text, nullable=True)
    transaction_ref = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    def __repr__(self):
        return f"SamPayment invoice={self.invoice_id}"


class SamPaymentDTO(BaseModel):
    id: int | None = None
    invoice_id: str | None = None
    telegram_id: int | None = None
    method: str | None = "shamcash"
    currency: str | None = "USD"
    amount: float | None = 0.0
    usd_amount: float | None = 0.0
    payment_url: str | None = None
    event: str | None = None
    transaction_ref: str | None = None
    created_at: datetime.datetime | None = None


class SamPaymentAdmin(ModelView, model=SamPayment):
    name = "SAM Payment"
    name_plural = "SAM Payments"
    icon = "fa-solid fa-wallet"
    category = "Payments"

    column_list = [SamPayment.id,
                   SamPayment.invoice_id,
                   SamPayment.telegram_id,
                   SamPayment.method,
                   SamPayment.currency,
                   SamPayment.amount,
                   SamPayment.usd_amount,
                   SamPayment.event,
                   SamPayment.transaction_ref,
                   SamPayment.created_at]
    column_labels = {
        SamPayment.id: "ID",
        SamPayment.invoice_id: "Invoice ID",
        SamPayment.telegram_id: "Telegram ID",
        SamPayment.method: "Method",
        SamPayment.currency: "Currency",
        SamPayment.amount: "Amount",
        SamPayment.usd_amount: "USD",
        SamPayment.event: "Event",
        SamPayment.transaction_ref: "Txn ref",
        SamPayment.created_at: "Created",
    }
    can_create = False
    can_edit = True
    can_delete = False