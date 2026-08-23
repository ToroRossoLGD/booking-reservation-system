"""create reservation transfers

Revision ID: f8b2d6e9a731
Revises: e7a1c9d4b620
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8b2d6e9a731"
down_revision: str | Sequence[str] | None = "e7a1c9d4b620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reservation_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("previous_owner_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=True),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("active_key", sa.String(50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reservations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["previous_owner_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("token_hash"),
        sa.UniqueConstraint("active_key"),
    )
    for column in (
        "reservation_id",
        "previous_owner_id",
        "recipient_user_id",
        "recipient_email",
        "token_hash",
        "expires_at",
    ):
        op.create_index(
            f"ix_reservation_transfers_{column}",
            "reservation_transfers",
            [column],
        )


def downgrade() -> None:
    op.drop_table("reservation_transfers")
