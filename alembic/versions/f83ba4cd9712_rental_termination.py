"""Mutual early rental termination and retained voided charges."""

import sqlalchemy as sa
from alembic import op

revision = "f83ba4cd9712"
down_revision = "e72a93bc8601"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "rental_agreements", sa.Column("terminated_on", sa.Date(), nullable=True)
    )
    op.add_column(
        "rental_charges",
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "rental_terminations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "agreement_id",
            sa.Integer(),
            sa.ForeignKey("rental_agreements.id"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "agreement_id", "request_id", name="uq_rental_termination_request"
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'declined', 'withdrawn')",
            name="ck_rental_termination_status",
        ),
    )
    op.create_index(
        "ix_rental_terminations_agreement_id", "rental_terminations", ["agreement_id"]
    )
    op.create_index(
        "uq_rental_termination_active",
        "rental_terminations",
        ["agreement_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('proposed', 'accepted')"),
        sqlite_where=sa.text("status IN ('proposed', 'accepted')"),
    )


def downgrade():
    op.drop_table("rental_terminations")
    op.drop_column("rental_charges", "voided_at")
    op.drop_column("rental_agreements", "terminated_on")
