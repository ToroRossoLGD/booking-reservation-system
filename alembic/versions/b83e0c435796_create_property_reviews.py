"""Add one verified property review per completed stay."""

import sqlalchemy as sa
from alembic import op

revision = "b83e0c435796"
down_revision = "a72d9b324685"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "property_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stay_id", sa.Integer(), sa.ForeignKey("stays.id"), nullable=False),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("property_listings.id"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("stay_id", name="uq_property_review_stay"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_property_review_rating"),
    )
    op.create_index(
        "ix_property_reviews_property_id", "property_reviews", ["property_id"]
    )


def downgrade():
    op.drop_table("property_reviews")
