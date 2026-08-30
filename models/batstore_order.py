import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, BigInteger, Float, Text, DateTime, JSON
from sqlalchemy.orm import relationship

from models.base import Base


class BatStoreOrder(Base):
    """Record of a fulfilled BatStore reseller order.

    `details` holds the per-line items: [{product_id, name, quantity, cost_usd,
    sell_usd, delivery_type, delivery_goods}]. `external_order_ref` is the
    reseller API order id when the upstream created one.
    """
    __tablename__ = "batstore_orders"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    total_sell = Column(Float, nullable=False, default=0.0)
    status = Column(Text, nullable=False, default="completed")
    external_order_ref = Column(Text, nullable=True)
    customer_reference = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    def __repr__(self):
        return f"BatStoreOrder ID: {self.id}"


class BatStoreOrderDTO(BaseModel):
    id: int | None = None
    telegram_id: int | None = None
    total_sell: float | None = None
    status: str | None = "completed"
    external_order_ref: str | None = None
    customer_reference: str | None = None
    details: list | None = None
    created_at: datetime.datetime | None = None


class BatStoreOrderAdmin(ModelView, model=BatStoreOrder):
    name = "GH Store Order"
    name_plural = "GH Store Orders"
    icon = "fa-solid fa-bag-shopping"
    category = "Catalog"

    column_list = [BatStoreOrder.id,
                   BatStoreOrder.telegram_id,
                   BatStoreOrder.total_sell,
                   BatStoreOrder.status,
                   BatStoreOrder.external_order_ref,
                   BatStoreOrder.customer_reference,
                   BatStoreOrder.created_at]
    column_labels = {
        BatStoreOrder.id: "ID",
        BatStoreOrder.telegram_id: "Telegram ID",
        BatStoreOrder.total_sell: "Total (USD)",
        BatStoreOrder.status: "Status",
        BatStoreOrder.external_order_ref: "Reseller order",
        BatStoreOrder.customer_reference: "Customer ref",
        BatStoreOrder.created_at: "Created",
    }
    can_create = True
    can_edit = True
    can_delete = False
