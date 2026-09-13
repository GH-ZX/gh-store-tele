"""Create wallet_ledger table and convert monetary columns to Numeric(12, 2).

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-13
"""
from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create wallet_ledger table
    op.create_table(
        "wallet_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("transaction_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance_before", sa.Numeric(12, 2), nullable=True),
        sa.Column("balance_after", sa.Numeric(12, 2), nullable=True),
        sa.Column("reference", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("batstore_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("supplier", sa.String(32), nullable=True),
        sa.Column("supplier_cost", sa.Numeric(12, 4), nullable=True),
        sa.Column("supplier_currency", sa.String(8), nullable=True, server_default="USD"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_ledger_tg_created", "wallet_ledger", ["telegram_id", "created_at"])
    op.create_index("idx_ledger_order", "wallet_ledger", ["order_id"])
    op.create_index("idx_ledger_tx_type", "wallet_ledger", ["transaction_type"])

    # 2. Alter float monetary columns to Numeric(12, 2)
    # Using postgresql_using to safely cast any existing floats
    op.alter_column(
        "users",
        "top_up_amount",
        type_=sa.Numeric(12, 2),
        postgresql_using="ROUND(COALESCE(top_up_amount, 0)::numeric, 2)",
        existing_type=sa.Float(),
        nullable=True,
    )
    op.alter_column(
        "users",
        "consume_records",
        type_=sa.Numeric(12, 2),
        postgresql_using="ROUND(COALESCE(consume_records, 0)::numeric, 2)",
        existing_type=sa.Float(),
        nullable=True,
    )
    op.alter_column(
        "batstore_orders",
        "total_sell",
        type_=sa.Numeric(12, 2),
        postgresql_using="ROUND(COALESCE(total_sell, 0)::numeric, 2)",
        existing_type=sa.Float(),
        nullable=False,
    )


def downgrade():
    op.alter_column("batstore_orders", "total_sell", type_=sa.Float(), existing_type=sa.Numeric(12, 2))
    op.alter_column("users", "consume_records", type_=sa.Float(), existing_type=sa.Numeric(12, 2))
    op.alter_column("users", "top_up_amount", type_=sa.Float(), existing_type=sa.Numeric(12, 2))
    op.drop_index("idx_ledger_tx_type", table_name="wallet_ledger")
    op.drop_index("idx_ledger_order", table_name="wallet_ledger")
    op.drop_index("idx_ledger_tg_created", table_name="wallet_ledger")
    op.drop_table("wallet_ledger")
