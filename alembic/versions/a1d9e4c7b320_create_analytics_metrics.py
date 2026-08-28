"""create daily analytics metrics

Revision ID: a1d9e4c7b320
Revises: 4c8a1e7d2f90, e2b8c5d1f704
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1d9e4c7b320"
down_revision: str | Sequence[str] | None = ("4c8a1e7d2f90", "e2b8c5d1f704")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _metric_columns(*, resource: bool = False) -> list[sa.Column]:
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
    ]
    if resource:
        columns.append(sa.Column("resource_id", sa.Integer(), nullable=False))
    columns.extend(
        [
            sa.Column("reservation_count", sa.Integer(), nullable=False),
            sa.Column("unique_customer_count", sa.Integer(), nullable=False),
            sa.Column("booked_minutes", sa.Integer(), nullable=False),
            sa.Column("booked_capacity_minutes", sa.Integer(), nullable=False),
            sa.Column("cancelled_count", sa.Integer(), nullable=False),
            sa.Column("no_show_count", sa.Integer(), nullable=False),
            sa.Column("reservations_by_status", sa.JSON(), nullable=False),
            sa.Column("revenue_by_currency", sa.JSON(), nullable=False),
            sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        ]
    )
    if resource:
        columns.append(
            sa.ForeignKeyConstraint(
                ["resource_id"], ["resources.id"], ondelete="CASCADE"
            )
        )
    return columns


def upgrade() -> None:
    op.create_table(
        "daily_venue_metrics",
        *_metric_columns(),
        sa.UniqueConstraint("metric_date", "venue_id", name="uq_daily_venue_metric"),
    )
    op.create_index(
        op.f("ix_daily_venue_metrics_metric_date"),
        "daily_venue_metrics",
        ["metric_date"],
    )
    op.create_index(
        op.f("ix_daily_venue_metrics_venue_id"),
        "daily_venue_metrics",
        ["venue_id"],
    )
    op.create_table(
        "daily_resource_metrics",
        *_metric_columns(resource=True),
        sa.UniqueConstraint(
            "metric_date", "resource_id", name="uq_daily_resource_metric"
        ),
    )
    for column in ("metric_date", "venue_id", "resource_id"):
        op.create_index(
            op.f(f"ix_daily_resource_metrics_{column}"),
            "daily_resource_metrics",
            [column],
        )


def downgrade() -> None:
    op.drop_table("daily_resource_metrics")
    op.drop_table("daily_venue_metrics")
