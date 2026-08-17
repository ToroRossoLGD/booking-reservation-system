"""add reservation idempotency

Revision ID: a62d9f3b7e41
Revises: e53a9d2f6b32
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a62d9f3b7e41"
down_revision: str | Sequence[str] | None = "e53a9d2f6b32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "reservations",
        sa.Column("idempotency_request_hash", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_reservations_user_idempotency_key",
        "reservations",
        ["user_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_reservations_user_idempotency_key",
        "reservations",
        type_="unique",
    )
    op.drop_column("reservations", "idempotency_request_hash")
    op.drop_column("reservations", "idempotency_key")
