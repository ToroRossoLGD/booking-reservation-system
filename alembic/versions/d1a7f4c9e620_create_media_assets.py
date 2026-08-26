"""create media assets

Revision ID: d1a7f4c9e620
Revises: c0f6a2d9e413
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1a7f4c9e620"
down_revision: str | None = "c0f6a2d9e413"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "venue_id",
            sa.Integer(),
            sa.ForeignKey("venues.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "resource_id",
            sa.Integer(),
            sa.ForeignKey("resources.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("object_key", sa.String(512), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(venue_id IS NOT NULL AND resource_id IS NULL) OR (venue_id IS NULL AND resource_id IS NOT NULL)",
            name="ck_media_assets_single_parent",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_media_assets_size_positive"),
    )
    op.create_index("ix_media_assets_venue_id", "media_assets", ["venue_id"])
    op.create_index("ix_media_assets_resource_id", "media_assets", ["resource_id"])


def downgrade() -> None:
    op.drop_index("ix_media_assets_resource_id", table_name="media_assets")
    op.drop_index("ix_media_assets_venue_id", table_name="media_assets")
    op.drop_table("media_assets")
