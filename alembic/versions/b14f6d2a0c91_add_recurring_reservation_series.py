"""add recurring reservation series

Revision ID: b14f6d2a0c91
Revises: 8c31c0a2f414
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b14f6d2a0c91"
down_revision: str | Sequence[str] | None = "8c31c0a2f414"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column("recurrence_series_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_reservations_recurrence_series_id"),
        "reservations",
        ["recurrence_series_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_reservations_recurrence_series_id"),
        table_name="reservations",
    )
    op.drop_column("reservations", "recurrence_series_id")
