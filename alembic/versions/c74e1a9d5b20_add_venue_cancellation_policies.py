"""add venue cancellation policies

Revision ID: c74e1a9d5b20
Revises: a62d9f3b7e41
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c74e1a9d5b20"
down_revision: str | Sequence[str] | None = "a62d9f3b7e41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column(
            "free_cancellation_hours",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
    )
    op.add_column(
        "venues",
        sa.Column(
            "late_cancellation_refund_percent",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "cancellation_free_hours",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "cancellation_late_refund_percent",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
    )
    op.create_check_constraint(
        "ck_venues_free_cancellation_hours",
        "venues",
        "free_cancellation_hours BETWEEN 0 AND 720",
    )
    op.create_check_constraint(
        "ck_venues_late_refund_percent",
        "venues",
        "late_cancellation_refund_percent BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_reservations_cancellation_free_hours",
        "reservations",
        "cancellation_free_hours BETWEEN 0 AND 720",
    )
    op.create_check_constraint(
        "ck_reservations_cancellation_late_refund_percent",
        "reservations",
        "cancellation_late_refund_percent BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_reservations_cancellation_late_refund_percent",
        "reservations",
        type_="check",
    )
    op.drop_constraint(
        "ck_reservations_cancellation_free_hours",
        "reservations",
        type_="check",
    )
    op.drop_constraint(
        "ck_venues_late_refund_percent", "venues", type_="check"
    )
    op.drop_constraint(
        "ck_venues_free_cancellation_hours", "venues", type_="check"
    )
    op.drop_column("reservations", "cancellation_late_refund_percent")
    op.drop_column("reservations", "cancellation_free_hours")
    op.drop_column("venues", "late_cancellation_refund_percent")
    op.drop_column("venues", "free_cancellation_hours")
