"""Add admin audit logs table

Revision ID: b3a2c1d0e9f8
Revises: f9e8d7c6b5a4
Create Date: 2026-09-04 07:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3a2c1d0e9f8'
down_revision: Union[str, None] = 'f9e8d7c6b5a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "admin_audit_logs" not in set(inspector.get_table_names()):
        op.create_table(
            "admin_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("admin_tg_id", sa.BigInteger(), nullable=False),
            sa.Column("action", sa.Text(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_admin_audit_logs_admin_tg_id", "admin_audit_logs", ["admin_tg_id"])
        op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("admin_audit_logs")
