"""add reservation pricing

Revision ID: c91e7a2d4b10
Revises: b14f6d2a0c91
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c91e7a2d4b10"
down_revision: str | Sequence[str] | None = "b14f6d2a0c91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "resources",
        sa.Column(
            "hourly_rate_cents",
            sa.Integer(),
            nullable=False,
            server_default="1000",
        ),
    )
    op.add_column(
        "resources",
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="EUR",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column("quoted_amount_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "reservations",
        sa.Column("quoted_currency", sa.String(length=3), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE reservations
            SET quoted_amount_cents = GREATEST(
                    1,
                    ROUND(
                        EXTRACT(EPOCH FROM (end_time - start_time)) * 1000 / 3600
                    )::integer
                ),
                quoted_currency = 'EUR'
            """
        )
    )
    op.alter_column("reservations", "quoted_amount_cents", nullable=False)
    op.alter_column("reservations", "quoted_currency", nullable=False)


def downgrade() -> None:
    op.drop_column("reservations", "quoted_currency")
    op.drop_column("reservations", "quoted_amount_cents")
    op.drop_column("resources", "currency")
    op.drop_column("resources", "hourly_rate_cents")
