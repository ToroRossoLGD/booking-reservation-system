"""add venue coordinates and Stripe checkout references

Revision ID: e2b8c5d1f704
Revises: d1a7f4c9e620
"""

from alembic import op
import sqlalchemy as sa

revision = "e2b8c5d1f704"
down_revision = "d1a7f4c9e620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("venues", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("venues", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_check_constraint("ck_venues_latitude", "venues", "latitude BETWEEN -90 AND 90")
    op.create_check_constraint("ck_venues_longitude", "venues", "longitude BETWEEN -180 AND 180")
    op.add_column("payments", sa.Column("provider_session_id", sa.String(length=255), nullable=True))
    op.create_index("ix_payments_provider_session_id", "payments", ["provider_session_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_payments_provider_session_id", table_name="payments")
    op.drop_column("payments", "provider_session_id")
    op.drop_constraint("ck_venues_longitude", "venues", type_="check")
    op.drop_constraint("ck_venues_latitude", "venues", type_="check")
    op.drop_column("venues", "longitude")
    op.drop_column("venues", "latitude")
