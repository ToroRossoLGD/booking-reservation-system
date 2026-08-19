"""add notification deduplication

Revision ID: 4c8a1e7d2f90
Revises: 0b7d4e2a91c3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c8a1e7d2f90"
down_revision: str | Sequence[str] | None = "0b7d4e2a91c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("deduplication_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_notifications_deduplication_key"),
        "notifications",
        ["deduplication_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_deduplication_key"), "notifications")
    op.drop_column("notifications", "deduplication_key")
