import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, BigInteger, Float, Text, DateTime, JSON, Boolean, Index, String, UniqueConstraint

from models.base import Base


class Order(Base):
    """Universal Digital Order Record.
    Backed by table 'batstore_orders' for seamless database continuity.
    Records fulfilled orders across all upstream suppliers (BatStore, ProdSeller, etc.).
    """
    __tablename__ = "batstore_orders"
    __table_args__ = (
        Index("idx_orders_status_created", "status", "created_at"),
        Index("idx_orders_tg_created", "telegram_id", "created_at"),
        UniqueConstraint("telegram_id", "checkout_key", name="uq_order_user_checkout_key"),
    )
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    total_sell = Column(Float, nullable=False, default=0.0)
    status = Column(Text, nullable=False, default="completed")
    external_order_ref = Column(Text, nullable=True)
    customer_reference = Column(Text, nullable=True)
    checkout_key = Column(String(128), nullable=True)
    request_fingerprint = Column(String(64), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    warranty_claimed = Column(Boolean, default=False, nullable=False)
    warranty_claimed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"Order ID: {self.id} [tg={self.telegram_id}, status={self.status}]"


class OrderDTO(BaseModel):
    id: int | None = None
    telegram_id: int | None = None
    total_sell: float | None = None
    status: str | None = "completed"
    external_order_ref: str | None = None
    customer_reference: str | None = None
    checkout_key: str | None = None
    request_fingerprint: str | None = None
    details: list | None = None
    created_at: datetime.datetime | None = None
    warranty_claimed: bool = False
    warranty_claimed_at: datetime.datetime | None = None


class OrderAdmin(ModelView, model=Order):
    name = "GH Store Order"
    name_plural = "GH Store Orders"
    icon = "fa-solid fa-bag-shopping"
    category = "Catalog"

    column_list = [
        Order.id,
        Order.telegram_id,
        Order.total_sell,
        Order.status,
        Order.external_order_ref,
        Order.customer_reference,
        Order.created_at
    ]
    column_labels = {
        Order.id: "ID",
        Order.telegram_id: "Telegram ID",
        Order.total_sell: "Total (USD)",
        Order.status: "Status",
        Order.external_order_ref: "Supplier order",
        Order.customer_reference: "Customer ref",
        Order.created_at: "Created",
    }
    can_create = True
    can_edit = True
    can_delete = False


# Backward-compatibility aliases
BatStoreOrder = Order
BatStoreOrderDTO = OrderDTO
BatStoreOrderAdmin = OrderAdmin
