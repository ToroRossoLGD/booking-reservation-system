"""add reservation party size

Revision ID: f29b7c4d8e10
Revises: d85f2b7c6a31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f29b7c4d8e10"
down_revision: str | Sequence[str] | None = "d85f2b7c6a31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column("party_size", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "ck_reservations_party_size_positive",
        "reservations",
        "party_size >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_reservations_party_size_positive",
        "reservations",
        type_="check",
    )
    op.drop_column("reservations", "party_size")
