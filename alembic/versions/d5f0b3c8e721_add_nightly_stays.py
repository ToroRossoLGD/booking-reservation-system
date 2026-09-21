"""Add opt-in whole-apartment nightly reservations.

Revision ID: d5f0b3c8e721
Revises: c4e9a2b7d610
"""

import sqlalchemy as sa
from alembic import op

revision = "d5f0b3c8e721"
down_revision = "c4e9a2b7d610"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("property_listings", sa.Column("booking_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("property_listings", sa.Column("max_guests", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("property_listings", sa.Column("minimum_nights", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("property_listings", sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Belgrade"))
    op.create_table(
        "stays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("property_listings.id"), nullable=False),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("guests", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("contact_email", sa.String(254), nullable=False),
        sa.Column("nightly_rate_cents", sa.BigInteger(), nullable=False),
        sa.Column("total_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "request_id", name="uq_stays_user_request"),
        sa.CheckConstraint("check_out > check_in", name="ck_stays_dates"),
        sa.CheckConstraint("guests BETWEEN 1 AND 100", name="ck_stays_guests"),
        sa.CheckConstraint("status IN ('confirmed', 'cancelled')", name="ck_stays_status"),
        sa.CheckConstraint("total_cents > 0 AND nightly_rate_cents > 0", name="ck_stays_price"),
    )
    for name in ("property_id", "venue_id", "user_id"):
        op.create_index(f"ix_stays_{name}", "stays", [name])


def downgrade():
    op.drop_table("stays")
    for name in ("timezone", "minimum_nights", "max_guests", "booking_enabled"):
        op.drop_column("property_listings", name)
