from datetime import UTC, date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RentalAgreement(Base):
    __tablename__ = "rental_agreements"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_id", name="uq_rental_agreement_request"),
        CheckConstraint(
            "status IN ('proposed', 'accepted', 'declined', 'withdrawn')",
            name="ck_rental_agreement_status",
        ),
        CheckConstraint(
            "end_date > start_date AND months BETWEEN 1 AND 120",
            name="ck_rental_agreement_dates",
        ),
        CheckConstraint(
            "monthly_cents > 0 AND deposit_cents >= 0",
            name="ck_rental_agreement_amounts",
        ),
        Index(
            "uq_rental_agreement_active",
            "inquiry_id",
            unique=True,
            postgresql_where=text("status IN ('proposed', 'accepted')"),
            sqlite_where=text("status IN ('proposed', 'accepted')"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(
        ForeignKey("rental_inquiries.id"), index=True
    )
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    tenant_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    months: Mapped[int]
    monthly_cents: Mapped[int] = mapped_column(BigInteger)
    deposit_cents: Mapped[int] = mapped_column(BigInteger)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminated_on: Mapped[date | None] = mapped_column(Date)


class RentalCharge(Base):
    __tablename__ = "rental_charges"
    __table_args__ = (
        UniqueConstraint("agreement_id", "sequence", name="uq_rental_charge_sequence"),
        CheckConstraint("amount_cents > 0", name="ck_rental_charge_amount"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    agreement_id: Mapped[int] = mapped_column(
        ForeignKey("rental_agreements.id"), index=True
    )
    sequence: Mapped[int]
    due_date: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    paid: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RentalChargeEvent(Base):
    __tablename__ = "rental_charge_events"
    __table_args__ = (
        UniqueConstraint("charge_id", "version", name="uq_rental_charge_event_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    charge_id: Mapped[int] = mapped_column(ForeignKey("rental_charges.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    paid: Mapped[bool]
    version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RentalTermination(Base):
    __tablename__ = "rental_terminations"
    __table_args__ = (
        UniqueConstraint(
            "agreement_id", "request_id", name="uq_rental_termination_request"
        ),
        CheckConstraint(
            "status IN ('proposed', 'accepted', 'declined', 'withdrawn')",
            name="ck_rental_termination_status",
        ),
        Index(
            "uq_rental_termination_active",
            "agreement_id",
            unique=True,
            postgresql_where=text("status IN ('proposed', 'accepted')"),
            sqlite_where=text("status IN ('proposed', 'accepted')"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    agreement_id: Mapped[int] = mapped_column(
        ForeignKey("rental_agreements.id"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36))
    end_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
