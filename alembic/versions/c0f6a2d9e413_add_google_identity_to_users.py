"""add Google identity to users

Revision ID: c0f6a2d9e413
Revises: b9e5d3f8a012
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c0f6a2d9e413"
down_revision: str | None = "b9e5d3f8a012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
