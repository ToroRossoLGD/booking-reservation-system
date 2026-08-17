"""add venue booking rules

Revision ID: d85f2b7c6a31
Revises: c74e1a9d5b20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d85f2b7c6a31"
down_revision: str | Sequence[str] | None = "c74e1a9d5b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RULE_COLUMNS = (
    ("minimum_booking_notice_minutes", 60),
    ("maximum_advance_booking_days", 365),
    ("minimum_booking_duration_minutes", 30),
    ("maximum_booking_duration_minutes", 480),
    ("max_active_reservations_per_customer", 10),
)


def upgrade() -> None:
    for column_name, default in RULE_COLUMNS:
        op.add_column(
            "venues",
            sa.Column(
                column_name,
                sa.Integer(),
                nullable=False,
                server_default=str(default),
            ),
        )

    op.create_check_constraint(
        "ck_venues_minimum_booking_notice_minutes",
        "venues",
        "minimum_booking_notice_minutes BETWEEN 0 AND 10080",
    )
    op.create_check_constraint(
        "ck_venues_maximum_advance_booking_days",
        "venues",
        "maximum_advance_booking_days BETWEEN 1 AND 730",
    )
    op.create_check_constraint(
        "ck_venues_minimum_booking_duration_minutes",
        "venues",
        "minimum_booking_duration_minutes BETWEEN 15 AND 1440",
    )
    op.create_check_constraint(
        "ck_venues_maximum_booking_duration_minutes",
        "venues",
        "maximum_booking_duration_minutes BETWEEN 15 AND 10080",
    )
    op.create_check_constraint(
        "ck_venues_booking_duration_range",
        "venues",
        "maximum_booking_duration_minutes >= minimum_booking_duration_minutes",
    )
    op.create_check_constraint(
        "ck_venues_max_active_reservations_per_customer",
        "venues",
        "max_active_reservations_per_customer BETWEEN 1 AND 100",
    )


def downgrade() -> None:
    for constraint_name in (
        "ck_venues_max_active_reservations_per_customer",
        "ck_venues_booking_duration_range",
        "ck_venues_maximum_booking_duration_minutes",
        "ck_venues_minimum_booking_duration_minutes",
        "ck_venues_maximum_advance_booking_days",
        "ck_venues_minimum_booking_notice_minutes",
    ):
        op.drop_constraint(constraint_name, "venues", type_="check")

    for column_name, _default in reversed(RULE_COLUMNS):
        op.drop_column("venues", column_name)
