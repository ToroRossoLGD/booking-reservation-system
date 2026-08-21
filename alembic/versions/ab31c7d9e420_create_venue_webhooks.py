"""create venue webhooks

Revision ID: ab31c7d9e420
Revises: 6a9c4e1f3d82
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ab31c7d9e420"
down_revision: str | Sequence[str] | None = "6a9c4e1f3d82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("event_types", sa.JSON(), nullable=False),
        sa.Column("signing_key", sa.String(36), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_webhook_subscriptions_venue_id", "webhook_subscriptions", ["venue_id"])
    op.create_index("ix_webhook_subscriptions_is_active", "webhook_subscriptions", ["is_active"])
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["webhook_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["reservation_events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("subscription_id", "event_id", name="uq_webhook_delivery_subscription_event"),
    )
    for column in ("subscription_id", "event_id", "event_type", "status", "next_attempt_at"):
        op.create_index(f"ix_webhook_deliveries_{column}", "webhook_deliveries", [column])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_subscriptions")
