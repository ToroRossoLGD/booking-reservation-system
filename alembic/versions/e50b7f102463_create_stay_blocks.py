"""Add owner-controlled unavailability for whole-apartment stays."""

import sqlalchemy as sa
from alembic import op

revision = "e50b7f102463"
down_revision = "d49a6e0f1352"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stay_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column(
            "created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("venue_id", "request_id", name="uq_stay_block_request"),
        sa.CheckConstraint("check_out > check_in", name="ck_stay_block_dates"),
    )
    op.create_index("ix_stay_blocks_venue_id", "stay_blocks", ["venue_id"])


def downgrade():
    op.drop_table("stay_blocks")
