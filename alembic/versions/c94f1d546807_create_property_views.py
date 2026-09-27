"""Track daily deduplicated property-detail views."""

import sqlalchemy as sa
from alembic import op

revision = "c94f1d546807"
down_revision = "b83e0c435796"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "property_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("property_listings.id"),
            nullable=False,
        ),
        sa.Column("viewed_on", sa.Date(), nullable=False),
        sa.Column("visitor_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "property_id", "viewed_on", "visitor_hash", name="uq_property_view_daily"
        ),
    )
    op.create_index("ix_property_views_property_id", "property_views", ["property_id"])
    op.create_index("ix_property_views_viewed_on", "property_views", ["viewed_on"])


def downgrade():
    op.drop_table("property_views")
