"""Add optional property details without guessing historical values."""

import sqlalchemy as sa
from alembic import op

revision = "a72d9b324685"
down_revision = "f61c8a213574"
branch_labels = None
depends_on = None


def upgrade():
    for name, type_ in (
        ("property_type", sa.String(20)),
        ("neighborhood", sa.String(100)),
        ("floor", sa.Integer()),
        ("heating", sa.String(20)),
        ("furnishing", sa.String(20)),
        ("has_elevator", sa.Boolean()),
        ("has_parking", sa.Boolean()),
        ("has_terrace", sa.Boolean()),
    ):
        op.add_column("property_listings", sa.Column(name, type_, nullable=True))


def downgrade():
    for name in (
        "has_terrace",
        "has_parking",
        "has_elevator",
        "furnishing",
        "heating",
        "floor",
        "neighborhood",
        "property_type",
    ):
        op.drop_column("property_listings", name)
