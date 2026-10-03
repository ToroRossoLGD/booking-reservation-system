"""Add guest-requested stay date changes."""

import sqlalchemy as sa

from alembic import op

revision = "fcd806435790"
down_revision = "ebc79532468f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stay_date_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stay_id",
            sa.Integer(),
            sa.ForeignKey("stays.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("quote", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("stay_id", "request_id", name="uq_stay_change_request"),
        sa.CheckConstraint("check_out > check_in", name="ck_stay_change_dates"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'withdrawn', 'expired')",
            name="ck_stay_change_status",
        ),
    )
    op.create_index("ix_stay_date_changes_stay_id", "stay_date_changes", ["stay_id"])
    op.create_index(
        "uq_stay_pending_change",
        "stay_date_changes",
        ["stay_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade():
    op.drop_table("stay_date_changes")
