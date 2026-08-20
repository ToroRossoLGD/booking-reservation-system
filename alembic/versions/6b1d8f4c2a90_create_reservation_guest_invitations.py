"""create reservation guest invitations

Revision ID: 6b1d8f4c2a90
Revises: 9e4b2c7a5d18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6b1d8f4c2a90"
down_revision: str | Sequence[str] | None = "9e4b2c7a5d18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reservation_guest_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("guest_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("reservation_id", "email", name="uq_guest_invitation_reservation_email"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_reservation_guest_invitations_reservation_id"), "reservation_guest_invitations", ["reservation_id"])
    op.create_index(op.f("ix_reservation_guest_invitations_token_hash"), "reservation_guest_invitations", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_reservation_guest_invitations_token_hash"), table_name="reservation_guest_invitations")
    op.drop_index(op.f("ix_reservation_guest_invitations_reservation_id"), table_name="reservation_guest_invitations")
    op.drop_table("reservation_guest_invitations")

