"""add payment refund details

Revision ID: 1f7eddd87cfc
Revises: 31aa8fa77d5c
Create Date: 2026-07-14 15:53:13.863350

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1f7eddd87cfc"
down_revision: Union[str, Sequence[str], None] = "31aa8fa77d5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "refunded_amount_cents",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "payments",
        sa.Column(
            "cancellation_fee_cents",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "payments",
        sa.Column(
            "refunded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.alter_column(
        "payments",
        "refunded_amount_cents",
        server_default=None,
    )

    op.alter_column(
        "payments",
        "cancellation_fee_cents",
        server_default=None,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_column(
        "payments",
        "refunded_at",
    )

    op.drop_column(
        "payments",
        "cancellation_fee_cents",
    )

    op.drop_column(
        "payments",
        "refunded_amount_cents",
    )
    # ### end Alembic commands ###
