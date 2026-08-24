"""create venue customer blocks

Revision ID: b9e5d3f8a012
Revises: a8d4c2e7f901
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9e5d3f8a012"
down_revision: str | Sequence[str] | None = "a8d4c2e7f901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "venue_customer_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_by_id", sa.Integer(), nullable=False),
        sa.Column("unblocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unblocked_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["blocked_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["unblocked_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "venue_id", "customer_id", name="uq_venue_customer_blocks_customer"
        ),
    )
    op.create_index(
        "ix_venue_customer_blocks_venue_id", "venue_customer_blocks", ["venue_id"]
    )
    op.create_index(
        "ix_venue_customer_blocks_customer_id",
        "venue_customer_blocks",
        ["customer_id"],
    )
    op.create_index(
        "ix_venue_customer_blocks_blocked_until",
        "venue_customer_blocks",
        ["blocked_until"],
    )


def downgrade() -> None:
    op.drop_table("venue_customer_blocks")
