"""Add GH Store reseller, config, restock, and payment tables

Revision ID: e8d7c6b5a4f3
Revises: 91c3856a8aa0
Create Date: 2026-09-04 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8d7c6b5a4f3'
down_revision: Union[str, None] = '91c3856a8aa0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. app_config
    if "app_config" not in existing_tables:
        op.create_table(
            "app_config",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(length=128), nullable=False),
            sa.Column("value", sa.String(), nullable=True),
            sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("description", sa.String(), nullable=True),
        )
        op.create_index("ix_app_config_key", "app_config", ["key"], unique=True)

    # 2. batstore_products
    if "batstore_products" not in existing_tables:
        op.create_table(
            "batstore_products",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("emoji", sa.String(), nullable=True),
            sa.Column("custom_emoji_id", sa.String(), nullable=True),
            sa.Column("image_url", sa.String(), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("standard_price_usd", sa.Float(), nullable=True),
            sa.Column("delivery_type", sa.String(), nullable=True),
            sa.Column("stock", sa.Integer(), nullable=True),
            sa.Column("warranty_days", sa.Integer(), nullable=True),
            sa.Column("margin_type", sa.String(), nullable=True),
            sa.Column("margin_value", sa.Float(), nullable=True),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("sell_price_usd", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("reseller_key_override", sa.String(), nullable=True),
        )
        op.create_index("ix_batstore_products_product_id", "batstore_products", ["product_id"], unique=True)
        op.create_index("ix_batstore_products_category", "batstore_products", ["category"])
    else:
        cols = {c["name"] for c in inspector.get_columns("batstore_products")}
        if "custom_emoji_id" not in cols:
            op.add_column("batstore_products", sa.Column("custom_emoji_id", sa.String(), nullable=True))

    # 3. batstore_orders
    if "batstore_orders" not in existing_tables:
        op.create_table(
            "batstore_orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("total_sell", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'completed'")),
            sa.Column("external_order_ref", sa.Text(), nullable=True),
            sa.Column("customer_reference", sa.Text(), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_batstore_orders_telegram_id", "batstore_orders", ["telegram_id"])

    # 4. sam_payments
    if "sam_payments" not in existing_tables:
        op.create_table(
            "sam_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("invoice_id", sa.Text(), nullable=False),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("method", sa.Text(), nullable=False, server_default=sa.text("'shamcash'")),
            sa.Column("currency", sa.Text(), nullable=False, server_default=sa.text("'USD'")),
            sa.Column("amount", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("usd_amount", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("payment_url", sa.Text(), nullable=True),
            sa.Column("event", sa.Text(), nullable=True),
            sa.Column("transaction_ref", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_sam_payments_invoice_id", "sam_payments", ["invoice_id"], unique=True)
        op.create_index("ix_sam_payments_telegram_id", "sam_payments", ["telegram_id"])

    # 5. restock_subscriptions
    if "restock_subscriptions" not in existing_tables:
        op.create_table(
            "restock_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("batstore_product_id", sa.Integer(), nullable=True),
            sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=True),
            sa.Column("language", sa.String(length=8), nullable=False, server_default=sa.text("'en'")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("telegram_id", "batstore_product_id", name="uq_tg_batstore_product"),
            sa.UniqueConstraint("telegram_id", "subcategory_id", name="uq_tg_subcategory"),
        )
        op.create_index("ix_restock_subscriptions_telegram_id", "restock_subscriptions", ["telegram_id"])
        op.create_index("ix_restock_subscriptions_batstore_product_id", "restock_subscriptions", ["batstore_product_id"])
        op.create_index("ix_restock_subscriptions_subcategory_id", "restock_subscriptions", ["subcategory_id"])

    # 6. stars_payments
    if "stars_payments" not in existing_tables:
        op.create_table(
            "stars_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("telegram_payment_charge_id", sa.Text(), nullable=False),
            sa.Column("provider_payment_charge_id", sa.Text(), nullable=True),
            sa.Column("stars_amount", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("usd_amount", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("invoice_payload", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_stars_payments_charge_id", "stars_payments", ["telegram_payment_charge_id"], unique=True)
        op.create_index("ix_stars_payments_telegram_id", "stars_payments", ["telegram_id"])


def downgrade() -> None:
    op.drop_table("stars_payments")
    op.drop_table("restock_subscriptions")
    op.drop_table("sam_payments")
    op.drop_table("batstore_orders")
    op.drop_table("batstore_products")
    op.drop_table("app_config")
