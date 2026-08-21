"""create maintenance work orders

Revision ID: bc42d8e1f530
Revises: ab31c7d9e420
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bc42d8e1f530"
down_revision: str | Sequence[str] | None = "ab31c7d9e420"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_work_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reported_by_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reported_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("venue_id", "resource_id", "priority", "status", "reported_by_id", "assigned_to_id", "due_at", "created_at"):
        op.create_index(f"ix_maintenance_work_orders_{column}", "maintenance_work_orders", [column])
    op.create_table(
        "maintenance_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("activity_type", sa.String(30), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["work_order_id"], ["maintenance_work_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("work_order_id", "actor_id", "activity_type", "created_at"):
        op.create_index(f"ix_maintenance_activities_{column}", "maintenance_activities", [column])


def downgrade() -> None:
    op.drop_table("maintenance_activities")
    op.drop_table("maintenance_work_orders")
