"""Revocable whole-apartment occupancy subscriptions."""

import sqlalchemy as sa

from alembic import op

revision = "b83f04e9c712"
down_revision = "a79b46c120de"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "occupancy_feeds",
        sa.Column(
            "venue_id", sa.Integer(), sa.ForeignKey("venues.id"), primary_key=True
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("property_listings.id"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("occupancy_feeds")
