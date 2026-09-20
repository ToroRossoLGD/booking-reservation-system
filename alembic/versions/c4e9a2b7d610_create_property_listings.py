"""Create property listings without changing existing booking resources.

Revision ID: c4e9a2b7d610
Revises: b2e6f8a1c430
"""

import sqlalchemy as sa
from alembic import op

revision = "c4e9a2b7d610"
down_revision = "b2e6f8a1c430"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "property_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("offer_type", sa.String(20), nullable=False),
        sa.Column("area_sqm", sa.Integer(), nullable=False),
        sa.Column("rooms", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("contact_email", sa.String(254), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.CheckConstraint("offer_type IN ('short_stay', 'long_term', 'sale')", name="ck_property_offer"),
        sa.CheckConstraint("price_cents BETWEEN 1 AND 1000000000000", name="ck_property_price"),
        sa.CheckConstraint("area_sqm BETWEEN 1 AND 100000", name="ck_property_area"),
        sa.CheckConstraint("rooms BETWEEN 0 AND 100", name="ck_property_rooms"),
    )
    for column in ("venue_id", "city", "offer_type", "is_published"):
        op.create_index(f"ix_property_listings_{column}", "property_listings", [column])


def downgrade():
    op.drop_table("property_listings")
