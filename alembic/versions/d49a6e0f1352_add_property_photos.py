"""Add ordered photos for property listings."""

import sqlalchemy as sa
from alembic import op

revision = "d49a6e0f1352"
down_revision = "c38f5d9e0241"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "property_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False, unique=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("property_id", "request_id", name="uq_property_photo_request"),
        sa.CheckConstraint("position >= 0", name="ck_property_photo_position"),
    )
    op.create_index("ix_property_photos_property_id", "property_photos", ["property_id"])


def downgrade():
    op.drop_table("property_photos")
