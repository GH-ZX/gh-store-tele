from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, UniqueConstraint, func
from models.base import Base

try:
    from sqladmin import ModelView
except ImportError:
    class ModelView:
        pass


class RestockSubscription(Base):
    __tablename__ = 'restock_subscriptions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    batstore_product_id = Column(Integer, nullable=True, index=True)
    subcategory_id = Column(Integer, ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=True, index=True)
    language = Column(String, default="en", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notified_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('telegram_id', 'batstore_product_id', name='uq_tg_batstore_product'),
        UniqueConstraint('telegram_id', 'subcategory_id', name='uq_tg_subcategory'),
    )

    def __repr__(self):
        return f"RestockSubscription[tg={self.telegram_id}, product={self.batstore_product_id or self.subcategory_id}]"


class RestockSubscriptionDTO(BaseModel):
    id: int | None = None
    telegram_id: int
    user_id: int | None = None
    batstore_product_id: int | None = None
    subcategory_id: int | None = None
    language: str = "en"
    created_at: datetime | None = None
    notified_at: datetime | None = None


class RestockSubscriptionAdmin(ModelView, model=RestockSubscription):
    name = "Restock Subscription"
    name_plural = "Restock Subscriptions"
    icon = "fa-solid fa-bell"
    category = "Catalog"

    column_list = [
        RestockSubscription.id,
        RestockSubscription.telegram_id,
        RestockSubscription.batstore_product_id,
        RestockSubscription.subcategory_id,
        RestockSubscription.language,
        RestockSubscription.created_at,
        RestockSubscription.notified_at,
    ]
    column_searchable_list = [RestockSubscription.telegram_id]
    column_sortable_list = [RestockSubscription.id, RestockSubscription.created_at]
    can_delete = True
    can_create = False
    can_edit = False
