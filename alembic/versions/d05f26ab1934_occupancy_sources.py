"""Track calendar sources and their exclusive block ownership."""

import sqlalchemy as sa

from alembic import op

revision = "d05f26ab1934"
down_revision = "c94e15fa0823"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "occupancy_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(16)),
        sa.UniqueConstraint("venue_id", "name", name="uq_occupancy_source_name"),
    )
    op.create_index("ix_occupancy_sources_venue_id", "occupancy_sources", ["venue_id"])
    op.create_table(
        "occupancy_source_blocks",
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("occupancy_sources.id"),
            primary_key=True,
        ),
        sa.Column(
            "block_id",
            sa.Integer(),
            sa.ForeignKey("stay_blocks.id"),
            primary_key=True,
            unique=True,
        ),
    )


def downgrade():
    op.drop_table("occupancy_source_blocks")
    op.drop_index("ix_occupancy_sources_venue_id", table_name="occupancy_sources")
    op.drop_table("occupancy_sources")
