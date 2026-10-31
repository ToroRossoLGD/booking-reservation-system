"""Encrypted calendar connections and background refresh leases."""

import sqlalchemy as sa

from alembic import op

revision = "e16a37bc2045"
down_revision = "d05f26ab1934"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "occupancy_syncs",
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("occupancy_sources.id"),
            primary_key=True,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("property_listings.id"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("encrypted_url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("allow_empty", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(24), nullable=False),
    )
    op.create_index(
        "ix_occupancy_sync_due", "occupancy_syncs", ["enabled", "next_run_at"]
    )


def downgrade():
    op.drop_index("ix_occupancy_sync_due", table_name="occupancy_syncs")
    op.drop_table("occupancy_syncs")
