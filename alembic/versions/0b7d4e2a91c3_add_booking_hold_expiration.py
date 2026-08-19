"""add booking hold expiration

Revision ID: 0b7d4e2a91c3
Revises: f29b7c4d8e10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0b7d4e2a91c3"
down_revision: str | Sequence[str] | None = "f29b7c4d8e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE reservations
        SET hold_expires_at = created_at + INTERVAL '15 minutes'
        WHERE status = 'pending'
        """
    )
    op.create_index(
        op.f("ix_reservations_hold_expires_at"),
        "reservations",
        ["hold_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_reservations_hold_expires_at"), "reservations")
    op.drop_column("reservations", "hold_expires_at")
