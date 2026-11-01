"""Selectable hourly or daily property email digest."""

import sqlalchemy as sa

from alembic import op

revision = "d61f82ab7590"
down_revision = "c50e71fa6489"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("property_email_digests") as batch:
        batch.add_column(
            sa.Column(
                "interval_hours", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch.create_check_constraint(
            "ck_email_digest_interval", "interval_hours IN (1, 24)"
        )


def downgrade():
    with op.batch_alter_table("property_email_digests") as batch:
        batch.drop_constraint("ck_email_digest_interval", type_="check")
        batch.drop_column("interval_hours")
