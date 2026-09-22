"""Store long-term rental inquiries and viewing proposals."""

import sqlalchemy as sa
from alembic import op

revision = "a19d72b6e430"
down_revision = "d5f0b3c8e721"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rental_inquiries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("property_listings.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("monthly_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("move_in", sa.Date(), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("owner_reply", sa.Text(), nullable=False),
        sa.Column("viewing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "request_id", name="uq_rental_inquiry_request"),
        sa.CheckConstraint("duration_months BETWEEN 1 AND 120", name="ck_rental_duration"),
        sa.CheckConstraint("status IN ('open', 'viewing_proposed', 'viewing_confirmed', 'closed', 'withdrawn')", name="ck_rental_inquiry_status"),
    )
    for column in ("property_id", "owner_id", "user_id"):
        op.create_index(f"ix_rental_inquiries_{column}", "rental_inquiries", [column])


def downgrade():
    op.drop_table("rental_inquiries")
