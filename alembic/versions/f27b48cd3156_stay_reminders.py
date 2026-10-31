"""Stay reminder preferences and durable delivery records."""

import sqlalchemy as sa

from alembic import op

revision = "f27b48cd3156"
down_revision = "e16a37bc2045"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stay_reminder_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "stay_reminder_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stay_id", sa.Integer(), sa.ForeignKey("stays.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "stay_id", "user_id", "kind", "event_date", name="uq_stay_reminder_delivery"
        ),
    )
    op.create_index(
        "ix_stay_reminder_deliveries_stay_id", "stay_reminder_deliveries", ["stay_id"]
    )


def downgrade():
    op.drop_index(
        "ix_stay_reminder_deliveries_stay_id", table_name="stay_reminder_deliveries"
    )
    op.drop_table("stay_reminder_deliveries")
    op.drop_table("stay_reminder_preferences")
