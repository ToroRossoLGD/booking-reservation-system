"""Add private sales inquiries, viewing history and conversations."""

import sqlalchemy as sa

from alembic import op

revision = "b2ea28657912"
down_revision = "a1d917546801"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sale_inquiries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("property_listings.id"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("asking_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("owner_reply", sa.Text(), nullable=False),
        sa.Column("viewing_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "request_id", name="uq_sale_inquiry_request"),
        sa.CheckConstraint(
            "status IN ('open', 'viewing_proposed', 'viewing_confirmed', "
            "'closed', 'withdrawn')",
            name="ck_sale_inquiry_status",
        ),
    )
    for column in ("property_id", "user_id", "owner_id"):
        op.create_index(f"ix_sale_inquiries_{column}", "sale_inquiries", [column])
    op.create_index(
        "uq_active_sale_inquiry",
        "sale_inquiries",
        ["user_id", "property_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('closed', 'withdrawn')"),
        sqlite_where=sa.text("status NOT IN ('closed', 'withdrawn')"),
    )
    op.create_table(
        "sale_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "inquiry_id",
            sa.Integer(),
            sa.ForeignKey("sale_inquiries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36)),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("viewing_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "inquiry_id", "sender_id", "request_id", name="uq_sale_message_request"
        ),
        sa.CheckConstraint(
            "kind IN ('message', 'propose', 'confirm', 'decline', 'close', 'withdraw')",
            name="ck_sale_message_kind",
        ),
    )
    op.create_index(
        "ix_sale_messages_inquiry_id_id", "sale_messages", ["inquiry_id", "id"]
    )


def downgrade():
    op.drop_table("sale_messages")
    op.drop_table("sale_inquiries")
