"""add reservation audit history

Revision ID: 91b4e2a6c0d3
Revises: d42f8c1e5a21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "91b4e2a6c0d3"
down_revision: str | Sequence[str] | None = "d42f8c1e5a21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reservation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reservations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        op.f("ix_reservation_events_reservation_id"),
        "reservation_events",
        ["reservation_id"],
    )
    op.create_index(
        op.f("ix_reservation_events_event_type"),
        "reservation_events",
        ["event_type"],
    )
    op.create_index(
        op.f("ix_reservation_events_actor_id"),
        "reservation_events",
        ["actor_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_reservation_events_actor_id"), "reservation_events")
    op.drop_index(op.f("ix_reservation_events_event_type"), "reservation_events")
    op.drop_index(
        op.f("ix_reservation_events_reservation_id"), "reservation_events"
    )
    op.drop_table("reservation_events")
