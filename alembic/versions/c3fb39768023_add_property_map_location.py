"""Add opt-in approximate property map coordinates."""

import sqlalchemy as sa

from alembic import op

revision = "c3fb39768023"
down_revision = "b2ea28657912"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("property_listings") as batch:
        batch.add_column(sa.Column("map_latitude", sa.Float(), nullable=True))
        batch.add_column(sa.Column("map_longitude", sa.Float(), nullable=True))
        batch.create_check_constraint(
            "ck_property_map_location",
            "(map_latitude IS NULL AND map_longitude IS NULL) OR "
            "(map_latitude IS NOT NULL AND map_longitude IS NOT NULL AND "
            "map_latitude BETWEEN -85 AND 85 AND map_longitude BETWEEN -180 AND 180)",
        )
        batch.create_index(
            "ix_property_map_location", ["map_latitude", "map_longitude"]
        )


def downgrade():
    with op.batch_alter_table("property_listings") as batch:
        batch.drop_index("ix_property_map_location")
        batch.drop_constraint("ck_property_map_location", type_="check")
        batch.drop_column("map_longitude")
        batch.drop_column("map_latitude")
