"""Rental proposals, accepted payment plans and manual payment audit."""

import sqlalchemy as sa

from alembic import op

revision = "e72a93bc8601"
down_revision = "d61f82ab7590"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rental_agreements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "inquiry_id",
            sa.Integer(),
            sa.ForeignKey("rental_inquiries.id"),
            nullable=False,
        ),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("monthly_cents", sa.BigInteger(), nullable=False),
        sa.Column("deposit_cents", sa.BigInteger(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "owner_id", "request_id", name="uq_rental_agreement_request"
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'declined', 'withdrawn')",
            name="ck_rental_agreement_status",
        ),
        sa.CheckConstraint(
            "end_date > start_date AND months BETWEEN 1 AND 120",
            name="ck_rental_agreement_dates",
        ),
        sa.CheckConstraint(
            "monthly_cents > 0 AND deposit_cents >= 0",
            name="ck_rental_agreement_amounts",
        ),
    )
    op.create_index(
        "ix_rental_agreements_inquiry_id", "rental_agreements", ["inquiry_id"]
    )
    op.create_index("ix_rental_agreements_venue_id", "rental_agreements", ["venue_id"])
    op.create_index(
        "uq_rental_agreement_active",
        "rental_agreements",
        ["inquiry_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('proposed', 'accepted')"),
        sqlite_where=sa.text("status IN ('proposed', 'accepted')"),
    )
    op.create_table(
        "rental_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "agreement_id",
            sa.Integer(),
            sa.ForeignKey("rental_agreements.id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "agreement_id", "sequence", name="uq_rental_charge_sequence"
        ),
        sa.CheckConstraint("amount_cents > 0", name="ck_rental_charge_amount"),
    )
    op.create_index(
        "ix_rental_charges_agreement_id", "rental_charges", ["agreement_id"]
    )
    op.create_table(
        "rental_charge_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "charge_id",
            sa.Integer(),
            sa.ForeignKey("rental_charges.id"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "charge_id", "version", name="uq_rental_charge_event_version"
        ),
    )
    op.create_index(
        "ix_rental_charge_events_charge_id", "rental_charge_events", ["charge_id"]
    )


def downgrade():
    op.drop_table("rental_charge_events")
    op.drop_table("rental_charges")
    op.drop_table("rental_agreements")
