"""Add owner-defined maximum nightly stay length."""

import sqlalchemy as sa
from alembic import op

revision = "fc724087913a"
down_revision = "eb613f768029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "property_listings",
        sa.Column("maximum_nights", sa.Integer(), nullable=False, server_default="90"),
    )


def downgrade():
    op.drop_column("property_listings", "maximum_nights")
