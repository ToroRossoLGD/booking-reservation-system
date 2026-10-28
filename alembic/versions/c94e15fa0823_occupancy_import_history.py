"""Store outcomes of confirmed manual occupancy imports."""

import sqlalchemy as sa

from alembic import op

revision = "c94e15fa0823"
down_revision = "b83f04e9c712"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "occupancy_import_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("existing", sa.Integer(), nullable=False),
        sa.Column("conflicts", sa.Integer(), nullable=False),
        sa.Column("ignored", sa.Integer(), nullable=False),
        sa.Column("clipped", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('applied', 'conflict')", name="ck_import_run_status"
        ),
    )
    op.create_index(
        "ix_occupancy_import_runs_venue_id_id",
        "occupancy_import_runs",
        ["venue_id", "id"],
    )


def downgrade():
    op.drop_index(
        "ix_occupancy_import_runs_venue_id_id", table_name="occupancy_import_runs"
    )
    op.drop_table("occupancy_import_runs")
