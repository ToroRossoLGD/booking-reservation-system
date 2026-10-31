"""Viewing reminder preferences and durable delivery records."""

import sqlalchemy as sa

from alembic import op

revision = "a38c59de4267"
down_revision = "f27b48cd3156"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "viewing_reminder_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "viewing_reminder_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rental_id", sa.Integer(), sa.ForeignKey("rental_inquiries.id")),
        sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sale_inquiries.id")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("viewing_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(rental_id IS NULL) <> (sale_id IS NULL)", name="ck_viewing_reminder_kind"
        ),
        sa.UniqueConstraint(
            "rental_id", "user_id", "viewing_at", name="uq_rental_reminder_delivery"
        ),
        sa.UniqueConstraint(
            "sale_id", "user_id", "viewing_at", name="uq_sale_reminder_delivery"
        ),
    )


def downgrade():
    op.drop_table("viewing_reminder_deliveries")
    op.drop_table("viewing_reminder_preferences")
