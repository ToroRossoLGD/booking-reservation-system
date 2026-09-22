"""Add private rental conversation history and read receipts."""

import sqlalchemy as sa
from alembic import op

revision = "b27e4c8d9130"
down_revision = "a19d72b6e430"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rental_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inquiry_id", sa.Integer(), sa.ForeignKey("rental_inquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36)),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("viewing_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("inquiry_id", "sender_id", "request_id", name="uq_rental_message_request"),
        sa.CheckConstraint("kind IN ('message', 'legacy_reply', 'propose', 'confirm', 'decline', 'close', 'withdraw')", name="ck_rental_message_kind"),
    )
    op.create_index("ix_rental_messages_inquiry_id_id", "rental_messages", ["inquiry_id", "id"])
    # Historical reply timestamps and earlier overwritten replies are unknown.
    op.execute(sa.text("""
        INSERT INTO rental_messages (inquiry_id, sender_id, kind, body, created_at)
        SELECT id, user_id, 'message', message, created_at FROM rental_inquiries
        ORDER BY id
    """))
    op.execute(sa.text("""
        INSERT INTO rental_messages (inquiry_id, sender_id, kind, body)
        SELECT id, owner_id, 'legacy_reply', owner_reply FROM rental_inquiries
        WHERE owner_reply <> '' ORDER BY id
    """))


def downgrade():
    op.drop_table("rental_messages")
