"""Model for tracking upstream supplier wholesale price increases."""
import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, Text, Float, DateTime
from models.base import Base


class ProductPriceAudit(Base):
    __tablename__ = "product_price_audits"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, nullable=False, index=True)
    product_name = Column(Text, nullable=False)
    old_cost = Column(Float, nullable=False)
    new_cost = Column(Float, nullable=False)
    delta_percent = Column(Float, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    def __repr__(self):
        return f"PriceAudit #{self.id} prod:{self.product_id} +{self.delta_percent}%"


class ProductPriceAuditDTO(BaseModel):
    id: int | None = None
    product_id: int
    product_name: str
    old_cost: float
    new_cost: float
    delta_percent: float
    detected_at: datetime.datetime | None = None


class ProductPriceAuditAdmin(ModelView, model=ProductPriceAudit):
    name = "Price Spike Audit"
    name_plural = "Price Spike Audits"
    icon = "fa-solid fa-chart-line"
    category = "Catalog"
    column_list = [
        ProductPriceAudit.id,
        ProductPriceAudit.product_id,
        ProductPriceAudit.product_name,
        ProductPriceAudit.old_cost,
        ProductPriceAudit.new_cost,
        ProductPriceAudit.delta_percent,
        ProductPriceAudit.detected_at,
    ]
    can_create = False
    can_edit = False
    can_delete = True
