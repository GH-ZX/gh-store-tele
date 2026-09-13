"""Persist checkout idempotency keys per customer."""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("batstore_orders", sa.Column("checkout_key", sa.String(128), nullable=True))
    op.add_column("batstore_orders", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_order_user_checkout_key", "batstore_orders", ["telegram_id", "checkout_key"])


def downgrade():
    op.drop_constraint("uq_order_user_checkout_key", "batstore_orders", type_="unique")
    op.drop_column("batstore_orders", "request_fingerprint")
    op.drop_column("batstore_orders", "checkout_key")
