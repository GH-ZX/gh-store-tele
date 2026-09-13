"""Admin-approved cross-supplier product equivalences for deterministic failover."""
from alembic import op
import sqlalchemy as sa

revision = "c9d8e7f6a5b4"
down_revision = "f5e6d7c8b9a0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "approved_equivalents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("equivalent_product_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "product_id", "equivalent_product_id", name="uq_approved_equiv_pair"
        ),
    )


def downgrade():
    op.drop_table("approved_equivalents")