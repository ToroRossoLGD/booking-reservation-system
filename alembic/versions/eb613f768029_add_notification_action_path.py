"""Add optional navigation to in-app notifications."""

import sqlalchemy as sa
from alembic import op

revision = "eb613f768029"
down_revision = "da502e657918"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notifications", sa.Column("action_path", sa.String(255), nullable=True)
    )


def downgrade():
    op.drop_column("notifications", "action_path")
