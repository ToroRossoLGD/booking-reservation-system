"""Add preparation days between nightly stays."""

from alembic import op
import sqlalchemy as sa

revision = "cfa57310246d"
down_revision = "be946209135c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "property_listings",
        sa.Column("preparation_days", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("property_listings", "preparation_days")
