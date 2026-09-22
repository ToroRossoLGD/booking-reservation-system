"""Add private saved property listings."""

import sqlalchemy as sa
from alembic import op

revision = "c38f5d9e0241"
down_revision = "b27e4c8d9130"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "favorite_properties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "property_id", name="uq_favorite_property_user_property"),
    )
    op.create_index("ix_favorite_properties_user_id", "favorite_properties", ["user_id"])
    op.create_index("ix_favorite_properties_property_id", "favorite_properties", ["property_id"])


def downgrade():
    op.drop_table("favorite_properties")
