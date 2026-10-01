"""Add owner-defined nightly booking windows."""

from alembic import op
import sqlalchemy as sa

revision = "be946209135c"
down_revision = "ad835198024b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "property_listings",
        sa.Column(
            "advance_notice_days", sa.Integer(), nullable=False, server_default="1"
        ),
    )
    op.add_column(
        "property_listings",
        sa.Column(
            "booking_window_days", sa.Integer(), nullable=False, server_default="365"
        ),
    )


def downgrade():
    op.drop_column("property_listings", "booking_window_days")
    op.drop_column("property_listings", "advance_notice_days")
