"""Add gift vouchers table

Revision ID: c4b3a2d1e0f9
Revises: b3a2c1d0e9f8
Create Date: 2026-09-04 08:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c4b3a2d1e0f9'
down_revision: Union[str, None] = 'b3a2c1d0e9f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "gift_vouchers" not in set(inspector.get_table_names()):
        op.create_table(
            "gift_vouchers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("amount_usd", sa.Float(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("redeemed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("is_redeemed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_gift_vouchers_code", "gift_vouchers", ["code"], unique=True)
        op.create_index("ix_gift_vouchers_is_redeemed", "gift_vouchers", ["is_redeemed"])


def downgrade() -> None:
    op.drop_table("gift_vouchers")
