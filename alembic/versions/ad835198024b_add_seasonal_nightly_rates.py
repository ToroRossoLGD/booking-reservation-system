"""Add seasonal listing prices and immutable nightly booking breakdowns."""

import sqlalchemy as sa
from alembic import op

revision = "ad835198024b"
down_revision = "fc724087913a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "property_listings",
        sa.Column("seasonal_rates", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("stays", sa.Column("nightly_prices", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("stays", "nightly_prices")
    op.drop_column("property_listings", "seasonal_rates")
