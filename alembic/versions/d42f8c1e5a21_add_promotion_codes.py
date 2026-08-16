"""add promotion codes

Revision ID: d42f8c1e5a21
Revises: c91e7a2d4b10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d42f8c1e5a21"
down_revision: str | Sequence[str] | None = "c91e7a2d4b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("redemption_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"]),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_promotions_code"), "promotions", ["code"], unique=True)
    op.create_index(
        op.f("ix_promotions_venue_id"), "promotions", ["venue_id"], unique=False
    )
    op.add_column(
        "reservations",
        sa.Column("base_amount_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "discount_amount_cents", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "reservations", sa.Column("promotion_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "reservations", sa.Column("promotion_code", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "reservations",
        sa.Column("promotion_discount_percent", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE reservations SET base_amount_cents = quoted_amount_cents")
    op.alter_column("reservations", "base_amount_cents", nullable=False)
    op.create_foreign_key(
        "fk_reservations_promotion_id",
        "reservations",
        "promotions",
        ["promotion_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_reservations_promotion_id"),
        "reservations",
        ["promotion_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_reservations_promotion_id"), table_name="reservations")
    op.drop_constraint(
        "fk_reservations_promotion_id", "reservations", type_="foreignkey"
    )
    op.drop_column("reservations", "promotion_discount_percent")
    op.drop_column("reservations", "promotion_code")
    op.drop_column("reservations", "promotion_id")
    op.drop_column("reservations", "discount_amount_cents")
    op.drop_column("reservations", "base_amount_cents")
    op.drop_index(op.f("ix_promotions_venue_id"), table_name="promotions")
    op.drop_index(op.f("ix_promotions_code"), table_name="promotions")
    op.drop_table("promotions")
