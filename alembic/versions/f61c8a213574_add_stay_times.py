"""Add optional local arrival/departure rules and reservation snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "f61c8a213574"
down_revision = "e50b7f102463"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("property_listings", "stays"):
        op.add_column(table, sa.Column("check_in_time", sa.String(5), nullable=True))
        op.add_column(table, sa.Column("check_out_time", sa.String(5), nullable=True))


def downgrade():
    for table in ("stays", "property_listings"):
        op.drop_column(table, "check_out_time")
        op.drop_column(table, "check_in_time")
