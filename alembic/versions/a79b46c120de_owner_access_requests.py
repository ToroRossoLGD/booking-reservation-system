"""Owner access requests and retained administrator decisions."""

import sqlalchemy as sa

from alembic import op

revision = "a79b46c120de"
down_revision = "e42a31f7c908"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "owner_access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("decision_note", sa.Text()),
        sa.UniqueConstraint("user_id", "request_id", name="uq_owner_access_retry"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_owner_access_status",
        ),
    )
    op.create_index(
        "ix_owner_access_requests_user_id", "owner_access_requests", ["user_id"]
    )
    op.create_index("ix_owner_access_queue", "owner_access_requests", ["status", "id"])
    op.create_index(
        "uq_owner_access_pending",
        "owner_access_requests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade():
    op.drop_table("owner_access_requests")
