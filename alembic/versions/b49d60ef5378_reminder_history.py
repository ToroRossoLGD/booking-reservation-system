"""Indexes for personal reminder delivery history."""

from alembic import op

revision = "b49d60ef5378"
down_revision = "a38c59de4267"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_stay_reminder_history",
        "stay_reminder_deliveries",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_viewing_reminder_history",
        "viewing_reminder_deliveries",
        ["user_id", "created_at", "id"],
    )


def downgrade():
    op.drop_index(
        "ix_viewing_reminder_history", table_name="viewing_reminder_deliveries"
    )
    op.drop_index("ix_stay_reminder_history", table_name="stay_reminder_deliveries")
