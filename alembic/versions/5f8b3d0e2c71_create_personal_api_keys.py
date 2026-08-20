"""create personal api keys

Revision ID: 5f8b3d0e2c71
Revises: 4e7a2c9d1b60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5f8b3d0e2c71"
down_revision: str | Sequence[str] | None = "4e7a2c9d1b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"])
    op.create_index(op.f("ix_api_keys_key_prefix"), "api_keys", ["key_prefix"])
    op.create_index(
        op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=True
    )
    op.create_index(op.f("ix_api_keys_expires_at"), "api_keys", ["expires_at"])
    op.create_index(op.f("ix_api_keys_revoked_at"), "api_keys", ["revoked_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_api_keys_revoked_at"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_expires_at"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_prefix"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_user_id"), table_name="api_keys")
    op.drop_table("api_keys")

