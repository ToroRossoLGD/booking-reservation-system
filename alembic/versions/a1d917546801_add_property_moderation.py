"""Add listing reports, suspension controls and moderation history."""

import sqlalchemy as sa

from alembic import op

revision = "a1d917546801"
down_revision = "fcd806435790"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("property_listings") as batch:
        batch.add_column(
            sa.Column(
                "moderation_state",
                sa.String(16),
                nullable=False,
                server_default="clear",
            )
        )
        batch.add_column(
            sa.Column(
                "moderation_version", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch.add_column(
            sa.Column("moderation_note", sa.Text(), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("moderation_appeal", sa.Text(), nullable=False, server_default="")
        )
        batch.create_check_constraint(
            "ck_property_moderation_state",
            "moderation_state IN ('clear', 'suspended', 'appealed')",
        )
        batch.create_check_constraint(
            "ck_property_moderation_publish",
            "NOT is_published OR moderation_state = 'clear'",
        )
    op.create_table(
        "property_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("property_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "request_id", name="uq_property_report_request"),
        sa.CheckConstraint(
            "status IN ('pending', 'dismissed', 'action_taken')",
            name="ck_property_report_status",
        ),
    )
    for column in ("property_id", "user_id", "status"):
        op.create_index(f"ix_property_reports_{column}", "property_reports", [column])
    op.create_index(
        "uq_pending_property_report",
        "property_reports",
        ["user_id", "property_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "property_moderation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("property_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column(
            "report_id",
            sa.Integer(),
            sa.ForeignKey("property_reports.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "actor_id", "request_id", name="uq_property_moderation_request"
        ),
    )
    op.create_index(
        "ix_property_moderation_events_property_id",
        "property_moderation_events",
        ["property_id"],
    )


def downgrade():
    op.drop_table("property_moderation_events")
    op.drop_table("property_reports")
    with op.batch_alter_table("property_listings") as batch:
        batch.drop_constraint("ck_property_moderation_publish", type_="check")
        batch.drop_constraint("ck_property_moderation_state", type_="check")
        for name in (
            "moderation_appeal",
            "moderation_note",
            "moderation_version",
            "moderation_state",
        ):
            batch.drop_column(name)
