"""Add saved-search opt-in and durable alert processing."""

import sqlalchemy as sa

from alembic import op

revision = "ebc79532468f"
down_revision = "dab68421357e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "saved_searches",
        sa.Column(
            "alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "saved_searches", sa.Column("alerts_since", sa.DateTime(timezone=True))
    )
    op.add_column(
        "property_listings", sa.Column("first_published_at", sa.DateTime(timezone=True))
    )
    op.create_index(
        "ix_property_listings_first_published_at",
        "property_listings",
        ["first_published_at"],
    )
    # Existing public listings are not new announcements after deployment.
    op.execute(
        "UPDATE property_listings SET first_published_at = CURRENT_TIMESTAMP WHERE is_published = true"
    )
    op.create_table(
        "saved_search_matches",
        sa.Column(
            "search_id",
            sa.Integer(),
            sa.ForeignKey("saved_searches.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("property_listings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("matched", sa.Boolean(), nullable=False),
    )


def downgrade():
    op.drop_table("saved_search_matches")
    op.drop_index(
        "ix_property_listings_first_published_at", table_name="property_listings"
    )
    op.drop_column("property_listings", "first_published_at")
    op.drop_column("saved_searches", "alerts_since")
    op.drop_column("saved_searches", "alerts_enabled")
