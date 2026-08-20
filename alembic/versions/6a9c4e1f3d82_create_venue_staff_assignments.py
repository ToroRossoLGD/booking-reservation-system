"""create venue staff assignments

Revision ID: 6a9c4e1f3d82
Revises: 5f8b3d0e2c71
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6a9c4e1f3d82"
down_revision: str | Sequence[str] | None = "5f8b3d0e2c71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "venue_staff",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assigned_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("venue_id", "user_id", name="uq_venue_staff_venue_user"),
    )
    op.create_index(op.f("ix_venue_staff_venue_id"), "venue_staff", ["venue_id"])
    op.create_index(op.f("ix_venue_staff_user_id"), "venue_staff", ["user_id"])
    op.create_index(op.f("ix_venue_staff_role"), "venue_staff", ["role"])
    op.create_index(op.f("ix_venue_staff_revoked_at"), "venue_staff", ["revoked_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_venue_staff_revoked_at"), table_name="venue_staff")
    op.drop_index(op.f("ix_venue_staff_role"), table_name="venue_staff")
    op.drop_index(op.f("ix_venue_staff_user_id"), table_name="venue_staff")
    op.drop_index(op.f("ix_venue_staff_venue_id"), table_name="venue_staff")
    op.drop_table("venue_staff")
