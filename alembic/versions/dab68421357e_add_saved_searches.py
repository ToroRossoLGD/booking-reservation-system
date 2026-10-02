"""Add account saved searches."""

import sqlalchemy as sa

from alembic import op

revision = "dab68421357e"
down_revision = "cfa57310246d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("path", sa.String(2000), nullable=False),
        sa.UniqueConstraint("user_id", "path", name="uq_saved_search_path"),
    )
    op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])


def downgrade():
    op.drop_table("saved_searches")
