"""Add extra_meta column to batstore_products

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    prod_cols = {c["name"] for c in inspector.get_columns("batstore_products")}
    if "extra_meta" not in prod_cols:
        op.add_column("batstore_products", sa.Column("extra_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    prod_cols = {c["name"] for c in inspector.get_columns("batstore_products")}
    if "extra_meta" in prod_cols:
        op.drop_column("batstore_products", "extra_meta")
