"""add review moderation

Revision ID: 7d3f9a2b6c41
Revises: 4c8a1e7d2f90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d3f9a2b6c41"
down_revision: str | Sequence[str] | None = "4c8a1e7d2f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "resource_reviews",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="visible"),
    )
    op.add_column(
        "resource_reviews", sa.Column("moderation_reason", sa.Text(), nullable=True)
    )
    op.add_column(
        "resource_reviews", sa.Column("moderated_by", sa.Integer(), nullable=True)
    )
    op.add_column(
        "resource_reviews",
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "resource_reviews", sa.Column("owner_response", sa.Text(), nullable=True)
    )
    op.add_column(
        "resource_reviews",
        sa.Column("owner_responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_resource_reviews_moderated_by_users",
        "resource_reviews",
        "users",
        ["moderated_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_resource_reviews_status"), "resource_reviews", ["status"]
    )

    op.create_table(
        "review_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_id"], ["resource_reviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "review_id", "reporter_id", name="uq_review_reports_review_reporter"
        ),
    )
    op.create_index(
        op.f("ix_review_reports_review_id"), "review_reports", ["review_id"]
    )
    op.create_index(
        op.f("ix_review_reports_reporter_id"), "review_reports", ["reporter_id"]
    )
    op.create_index(op.f("ix_review_reports_reason"), "review_reports", ["reason"])
    op.create_index(op.f("ix_review_reports_status"), "review_reports", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_review_reports_status"), "review_reports")
    op.drop_index(op.f("ix_review_reports_reason"), "review_reports")
    op.drop_index(op.f("ix_review_reports_reporter_id"), "review_reports")
    op.drop_index(op.f("ix_review_reports_review_id"), "review_reports")
    op.drop_table("review_reports")
    op.drop_index(op.f("ix_resource_reviews_status"), "resource_reviews")
    op.drop_constraint(
        "fk_resource_reviews_moderated_by_users",
        "resource_reviews",
        type_="foreignkey",
    )
    op.drop_column("resource_reviews", "owner_responded_at")
    op.drop_column("resource_reviews", "owner_response")
    op.drop_column("resource_reviews", "moderated_at")
    op.drop_column("resource_reviews", "moderated_by")
    op.drop_column("resource_reviews", "moderation_reason")
    op.drop_column("resource_reviews", "status")
