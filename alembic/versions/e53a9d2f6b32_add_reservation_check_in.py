"""add reservation check in

Revision ID: e53a9d2f6b32
Revises: d42f8c1e5a21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e53a9d2f6b32"
down_revision: str | Sequence[str] | None = "d42f8c1e5a21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column("attendance_status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "reservations",
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "reservations",
        sa.Column("no_show_marked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE reservations
        SET attendance_status = CASE
                WHEN status = 'completed' THEN 'checked_in'
                ELSE 'scheduled'
            END,
            checked_in_at = CASE
                WHEN status = 'completed' THEN end_time
                ELSE NULL
            END
        """
    )
    op.alter_column("reservations", "attendance_status", nullable=False)
    op.create_index(
        "ix_reservations_attendance_status",
        "reservations",
        ["attendance_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reservations_attendance_status", table_name="reservations")
    op.drop_column("reservations", "no_show_marked_at")
    op.drop_column("reservations", "checked_in_at")
    op.drop_column("reservations", "attendance_status")
