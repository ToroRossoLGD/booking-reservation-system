"""Add long-term listing terms and inquiry snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "da502e657918"
down_revision = "c94f1d546807"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("property_listings", "rental_inquiries"):
        for name, type_ in (
            ("deposit_cents", sa.BigInteger()),
            ("monthly_bills_cents", sa.BigInteger()),
            ("available_from", sa.Date()),
            ("minimum_rental_months", sa.Integer()),
            ("pets_policy", sa.String(20)),
        ):
            op.add_column(table, sa.Column(name, type_, nullable=True))


def downgrade():
    for table in ("rental_inquiries", "property_listings"):
        for field in (
            "pets_policy",
            "minimum_rental_months",
            "available_from",
            "monthly_bills_cents",
            "deposit_cents",
        ):
            op.drop_column(table, field)
