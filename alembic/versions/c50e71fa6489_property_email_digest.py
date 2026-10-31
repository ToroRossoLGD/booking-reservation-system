"""Opt-in property notification email digests."""

import sqlalchemy as sa

from alembic import op

revision = "c50e71fa6489"
down_revision = "b49d60ef5378"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "property_email_digest_items",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("notification_id", sa.Integer(), primary_key=True),
    )
    op.create_table(
        "property_email_digests",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("cursor", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(24), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_accepted_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_property_email_digest_due",
        "property_email_digests",
        ["enabled", "next_run_at"],
    )


def downgrade():
    op.drop_table("property_email_digest_items")
    op.drop_index("ix_property_email_digest_due", table_name="property_email_digests")
    op.drop_table("property_email_digests")
