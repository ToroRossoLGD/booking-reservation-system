"""create digital waivers

Revision ID: e7a1c9d4b620
Revises: cd53e9f2a640
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7a1c9d4b620"
down_revision: str | Sequence[str] | None = "cd53e9f2a640"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waiver_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_waiver_templates_venue_id", "waiver_templates", ["venue_id"])

    op.create_table(
        "waiver_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("published_by_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"], ["waiver_templates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["published_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "template_id", "version", name="uq_waiver_versions_template_version"
        ),
    )
    op.create_index(
        "ix_waiver_versions_template_id", "waiver_versions", ["template_id"]
    )
    op.create_index(
        "ix_waiver_versions_published_by_id",
        "waiver_versions",
        ["published_by_id"],
    )

    op.create_table(
        "waiver_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("waiver_version_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("signer_name", sa.String(200), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reservations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["waiver_version_id"], ["waiver_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "reservation_id",
            "waiver_version_id",
            "user_id",
            name="uq_waiver_acceptances_reservation_version_user",
        ),
    )
    for column in ("reservation_id", "waiver_version_id", "user_id"):
        op.create_index(
            f"ix_waiver_acceptances_{column}", "waiver_acceptances", [column]
        )


def downgrade() -> None:
    op.drop_table("waiver_acceptances")
    op.drop_table("waiver_versions")
    op.drop_table("waiver_templates")
