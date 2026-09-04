"""Add currency preference and warranty fields

Revision ID: f9e8d7c6b5a4
Revises: e8d7c6b5a4f3
Create Date: 2026-09-04 06:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f9e8d7c6b5a4'
down_revision: Union[str, None] = 'e8d7c6b5a4f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. users.currency_preference
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "currency_preference" not in user_cols:
        op.add_column("users", sa.Column("currency_preference", sa.String(length=8), nullable=False, server_default="USD"))

    # 2. batstore_orders warranty fields
    if "batstore_orders" in set(inspector.get_table_names()):
        order_cols = {c["name"] for c in inspector.get_columns("batstore_orders")}
        if "warranty_claimed" not in order_cols:
            op.add_column("batstore_orders", sa.Column("warranty_claimed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        if "warranty_claimed_at" not in order_cols:
            op.add_column("batstore_orders", sa.Column("warranty_claimed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("batstore_orders", "warranty_claimed_at")
    op.drop_column("batstore_orders", "warranty_claimed")
    op.drop_column("users", "currency_preference")
