"""create calendar feeds

Revision ID: cd53e9f2a640
Revises: bc42d8e1f530
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cd53e9f2a640"
down_revision: str | Sequence[str] | None = "bc42d8e1f530"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_feeds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_prefix", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("include_pending", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("venue_id", "resource_id", "token_prefix", "revoked_at"):
        op.create_index(f"ix_calendar_feeds_{column}", "calendar_feeds", [column])


def downgrade() -> None:
    op.drop_table("calendar_feeds")
