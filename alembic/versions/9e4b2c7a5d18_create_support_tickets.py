"""create support tickets

Revision ID: 9e4b2c7a5d18
Revises: 7d3f9a2b6c41
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e4b2c7a5d18"
down_revision: str | Sequence[str] | None = "7d3f9a2b6c41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("assigned_admin_id", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assigned_admin_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        op.f("ix_support_tickets_creator_id"), "support_tickets", ["creator_id"]
    )
    op.create_index(
        op.f("ix_support_tickets_assigned_admin_id"),
        "support_tickets",
        ["assigned_admin_id"],
    )
    op.create_index(
        op.f("ix_support_tickets_category"), "support_tickets", ["category"]
    )
    op.create_index(
        op.f("ix_support_tickets_priority"), "support_tickets", ["priority"]
    )
    op.create_index(
        op.f("ix_support_tickets_status"), "support_tickets", ["status"]
    )

    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_support_messages_ticket_id"), "support_messages", ["ticket_id"]
    )
    op.create_index(
        op.f("ix_support_messages_author_id"), "support_messages", ["author_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_support_messages_author_id"), "support_messages")
    op.drop_index(op.f("ix_support_messages_ticket_id"), "support_messages")
    op.drop_table("support_messages")
    op.drop_index(op.f("ix_support_tickets_status"), "support_tickets")
    op.drop_index(op.f("ix_support_tickets_priority"), "support_tickets")
    op.drop_index(op.f("ix_support_tickets_category"), "support_tickets")
    op.drop_index(op.f("ix_support_tickets_assigned_admin_id"), "support_tickets")
    op.drop_index(op.f("ix_support_tickets_creator_id"), "support_tickets")
    op.drop_table("support_tickets")
