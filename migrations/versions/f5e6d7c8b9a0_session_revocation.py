"""Add per-user session revocation timestamp.

Blocking all sessions issued at-or-before this instant (token embeds iat).
"""
from alembic import op
import sqlalchemy as sa

revision = "f5e6d7c8b9a0"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("sessions_revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("users", "sessions_revoked_at")