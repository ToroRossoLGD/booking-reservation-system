"""create analytics pipeline runs

Revision ID: b2e6f8a1c430
Revises: a1d9e4c7b320
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2e6f8a1c430"
down_revision: str | Sequence[str] | None = "a1d9e4c7b320"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_pipeline_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("source_reservation_count", sa.Integer(), nullable=False),
        sa.Column("venue_metric_count", sa.Integer(), nullable=False),
        sa.Column("resource_metric_count", sa.Integer(), nullable=False),
        sa.Column("quality_checks_passed", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_analytics_pipeline_runs_completed_at"),
        "analytics_pipeline_runs",
        ["completed_at"],
    )


def downgrade() -> None:
    op.drop_table("analytics_pipeline_runs")
