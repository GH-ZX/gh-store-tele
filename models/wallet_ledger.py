import datetime
from decimal import Decimal
from sqladmin import ModelView
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Numeric,
    Text,
    String,
    DateTime,
    ForeignKey,
    Index
)

from models.base import Base


class WalletLedger(Base):
    """Immutable, append-only wallet transaction ledger.
    Records every balance credit, reservation (hold), capture, refund, and adjustment.
    Retains actual supplier cost and wholesale currency at purchase time.
    """
    __tablename__ = "wallet_ledger"
    __table_args__ = (
        Index("idx_ledger_tg_created", "telegram_id", "created_at"),
        Index("idx_ledger_order", "order_id"),
        Index("idx_ledger_ref", "reference", unique=True),
        Index("idx_ledger_tx_type", "transaction_type"),
    )

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    transaction_type = Column(String(32), nullable=False)  # credit, reservation, capture, refund, adjustment
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False)
    balance_before = Column(Numeric(12, 2, asdecimal=True), nullable=True)
    balance_after = Column(Numeric(12, 2, asdecimal=True), nullable=True)
    reference = Column(String(128), nullable=False, unique=True, index=True)
    order_id = Column(Integer, ForeignKey("batstore_orders.id", ondelete="SET NULL"), nullable=True)
    supplier = Column(String(32), nullable=True)
    supplier_cost = Column(Numeric(12, 4, asdecimal=True), nullable=True)
    supplier_currency = Column(String(8), nullable=True, default="USD")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    def __repr__(self):
        return f"<WalletLedger {self.id}: tg={self.telegram_id} {self.transaction_type} ${self.amount} ref={self.reference}>"


class WalletLedgerAdmin(ModelView, model=WalletLedger):
    name = "Wallet Ledger"
    name_plural = "Wallet Ledger Entries"
    icon = "fa-solid fa-book-journal-whills"
    category = "Finance"

    column_list = [
        WalletLedger.id,
        WalletLedger.telegram_id,
        WalletLedger.transaction_type,
        WalletLedger.amount,
        WalletLedger.balance_after,
        WalletLedger.reference,
        WalletLedger.order_id,
        WalletLedger.supplier,
        WalletLedger.supplier_cost,
        WalletLedger.created_at,
    ]
    column_searchable_list = [WalletLedger.telegram_id, WalletLedger.reference]
    column_sortable_list = [WalletLedger.id, WalletLedger.created_at, WalletLedger.amount]
    column_default_sort = ("created_at", True)
    can_create = False
    can_edit = False
    can_delete = False
