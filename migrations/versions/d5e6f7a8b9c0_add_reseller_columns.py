"""Add reseller columns to products and users

Revision ID: d5e6f7a8b9c0
Revises: c4b3a2d1e0f9
Create Date: 2026-09-07 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4b3a2d1e0f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    prod_cols = {c["name"] for c in inspector.get_columns("batstore_products")}
    if "reseller_price_usd" not in prod_cols:
        op.add_column("batstore_products", sa.Column("reseller_price_usd", sa.Float(), nullable=True))
    if "reseller_margin_pct" not in prod_cols:
        op.add_column("batstore_products", sa.Column("reseller_margin_pct", sa.Float(), nullable=True))

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_reseller" not in user_cols:
        op.add_column("users", sa.Column("is_reseller", sa.Boolean(), server_default=sa.text("false"), nullable=False))
        op.create_index("ix_users_is_reseller", "users", ["is_reseller"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_reseller" in user_cols:
        op.drop_index("ix_users_is_reseller", table_name="users")
        op.drop_column("users", "is_reseller")

    prod_cols = {c["name"] for c in inspector.get_columns("batstore_products")}
    if "reseller_margin_pct" in prod_cols:
        op.drop_column("batstore_products", "reseller_margin_pct")
    if "reseller_price_usd" in prod_cols:
        op.drop_column("batstore_products", "reseller_price_usd")
