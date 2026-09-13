import datetime
from sqladmin import ModelView
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Float,
    Text,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index
)

from models.base import Base


class SmsActivation(Base):
    """Stores dedicated SMS activation sessions (e.g. from 5sim).
    Tracks virtual number allocation, incoming SMS codes, expiration timeouts,
    and refund states.
    """
    __tablename__ = "sms_activations"
    __table_args__ = (
        Index("idx_sms_act_tg_status", "telegram_id", "status"),
        Index("idx_sms_act_order", "order_id"),
        Index("idx_sms_act_upstream", "activation_id"),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("batstore_orders.id", ondelete="SET NULL"), nullable=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    activation_id = Column(String(64), nullable=False, index=True)
    service = Column(String(64), nullable=False)
    country = Column(String(64), nullable=False)
    operator = Column(String(64), nullable=False, default="any")
    phone = Column(String(64), nullable=False)
    sms_code = Column(String(32), nullable=True)
    sms_text = Column(Text, nullable=True)
    cost_rub = Column(Float, nullable=False, default=0.0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    sell_price_usd = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="pending")  # pending, received, finished, canceled, timeout, banned
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    def __repr__(self):
        return f"<SmsActivation {self.id}: {self.service} ({self.country}) {self.phone} [{self.status}]>"


class SmsServiceConfig(Base):
    """Admin-curated list of popular SMS activation services."""
    __tablename__ = "sms_service_configs"

    id = Column(Integer, primary_key=True)
    service_code = Column(String(64), unique=True, nullable=False, index=True)
    name_en = Column(String(128), nullable=False)
    name_ar = Column(String(128), nullable=False)
    icon = Column(String(64), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<SmsServiceConfig {self.service_code}: {self.name_en} enabled={self.is_enabled}>"


class SmsCountryConfig(Base):
    """Admin-curated list of high-success / good-rate countries for SMS activations."""
    __tablename__ = "sms_country_configs"

    id = Column(Integer, primary_key=True)
    country_code = Column(String(64), unique=True, nullable=False, index=True)
    name_en = Column(String(128), nullable=False)
    name_ar = Column(String(128), nullable=False)
    flag_emoji = Column(String(16), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<SmsCountryConfig {self.country_code}: {self.name_en} enabled={self.is_enabled}>"


class SmsActivationAdmin(ModelView, model=SmsActivation):
    name = "SMS Activation"
    name_plural = "SMS Activations"
    icon = "fa-solid fa-sim-card"
    category = "Catalog"

    column_list = [
        SmsActivation.id,
        SmsActivation.order_id,
        SmsActivation.telegram_id,
        SmsActivation.activation_id,
        SmsActivation.service,
        SmsActivation.country,
        SmsActivation.phone,
        SmsActivation.sms_code,
        SmsActivation.status,
        SmsActivation.sell_price_usd,
        SmsActivation.expires_at,
        SmsActivation.created_at,
    ]
    column_searchable_list = [SmsActivation.phone, SmsActivation.activation_id, SmsActivation.telegram_id]
    column_sortable_list = [SmsActivation.id, SmsActivation.status, SmsActivation.created_at, SmsActivation.expires_at]


class SmsServiceConfigAdmin(ModelView, model=SmsServiceConfig):
    name = "SMS Service Option"
    name_plural = "SMS Service Options"
    icon = "fa-solid fa-list-check"
    category = "Catalog"

    column_list = [
        SmsServiceConfig.id,
        SmsServiceConfig.service_code,
        SmsServiceConfig.name_en,
        SmsServiceConfig.name_ar,
        SmsServiceConfig.is_enabled,
        SmsServiceConfig.sort_order,
    ]
    column_searchable_list = [SmsServiceConfig.service_code, SmsServiceConfig.name_en, SmsServiceConfig.name_ar]


class SmsCountryConfigAdmin(ModelView, model=SmsCountryConfig):
    name = "SMS Country Option"
    name_plural = "SMS Country Options"
    icon = "fa-solid fa-globe"
    category = "Catalog"

    column_list = [
        SmsCountryConfig.id,
        SmsCountryConfig.country_code,
        SmsCountryConfig.name_en,
        SmsCountryConfig.name_ar,
        SmsCountryConfig.flag_emoji,
        SmsCountryConfig.is_enabled,
        SmsCountryConfig.sort_order,
    ]
    column_searchable_list = [SmsCountryConfig.country_code, SmsCountryConfig.name_en, SmsCountryConfig.name_ar]
