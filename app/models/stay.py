from datetime import UTC, date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Stay(Base):
    __tablename__ = "stays"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_stays_user_request"),
        CheckConstraint("check_out > check_in", name="ck_stays_dates"),
        CheckConstraint("guests BETWEEN 1 AND 100", name="ck_stays_guests"),
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="ck_stays_status"),
        CheckConstraint(
            "total_cents > 0 AND nightly_rate_cents > 0", name="ck_stays_price"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id"), index=True
    )
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    guests: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    title: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64))
    check_in_time: Mapped[str | None] = mapped_column(String(5))
    check_out_time: Mapped[str | None] = mapped_column(String(5))
    contact_email: Mapped[str] = mapped_column(String(254))
    nightly_rate_cents: Mapped[int] = mapped_column(BigInteger)
    total_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
