"""create waitlist entries

Revision ID: 8c31c0a2f414
Revises: 1f7eddd87cfc
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8c31c0a2f414"
down_revision: str | Sequence[str] | None = "1f7eddd87cfc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_waitlist_entries_user_id"), "waitlist_entries", ["user_id"]
    )
    op.create_index(
        op.f("ix_waitlist_entries_resource_id"),
        "waitlist_entries",
        ["resource_id"],
    )
    op.create_index(
        op.f("ix_waitlist_entries_start_time"),
        "waitlist_entries",
        ["start_time"],
    )
    op.create_index(
        op.f("ix_waitlist_entries_end_time"), "waitlist_entries", ["end_time"]
    )
    op.create_index(op.f("ix_waitlist_entries_status"), "waitlist_entries", ["status"])
    op.create_index(
        "uq_waitlist_entries_waiting_slot",
        "waitlist_entries",
        ["user_id", "resource_id", "start_time", "end_time"],
        unique=True,
        postgresql_where=sa.text("status = 'waiting'"),
    )


def downgrade() -> None:
    op.drop_index("uq_waitlist_entries_waiting_slot", table_name="waitlist_entries")
    op.drop_index(op.f("ix_waitlist_entries_status"), table_name="waitlist_entries")
    op.drop_index(op.f("ix_waitlist_entries_end_time"), table_name="waitlist_entries")
    op.drop_index(op.f("ix_waitlist_entries_start_time"), table_name="waitlist_entries")
    op.drop_index(
        op.f("ix_waitlist_entries_resource_id"), table_name="waitlist_entries"
    )
    op.drop_index(op.f("ix_waitlist_entries_user_id"), table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
