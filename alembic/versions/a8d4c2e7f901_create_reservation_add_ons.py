"""create reservation add-ons

Revision ID: a8d4c2e7f901
Revises: f8b2d6e9a731
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8d4c2e7f901"
down_revision: str | Sequence[str] | None = "f8b2d6e9a731"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "add_ons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price_cents >= 0", name="ck_add_ons_price_nonnegative"),
        sa.CheckConstraint("stock >= 1", name="ck_add_ons_stock_positive"),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_add_ons_venue_id", "add_ons", ["venue_id"])

    op.add_column(
        "reservations",
        sa.Column("add_on_total_cents", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "reservation_add_ons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("add_on_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 1", name="ck_reservation_add_ons_quantity_positive"
        ),
        sa.CheckConstraint(
            "unit_price_cents >= 0", name="ck_reservation_add_ons_price_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reservations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["add_on_id"], ["add_ons.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_reservation_add_ons_reservation_id", "reservation_add_ons", ["reservation_id"]
    )
    op.create_index(
        "ix_reservation_add_ons_add_on_id", "reservation_add_ons", ["add_on_id"]
    )


def downgrade() -> None:
    op.drop_table("reservation_add_ons")
    op.drop_column("reservations", "add_on_total_cents")
    op.drop_table("add_ons")
