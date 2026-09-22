from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RentalInquiry(Base):
    __tablename__ = "rental_inquiries"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_rental_inquiry_request"),
        CheckConstraint(
            "status IN ('open', 'viewing_proposed', 'viewing_confirmed', "
            "'closed', 'withdrawn')",
            name="ck_rental_inquiry_status",
        ),
        CheckConstraint("duration_months BETWEEN 1 AND 120", name="ck_rental_duration"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(160))
    monthly_price_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    move_in: Mapped[date] = mapped_column(Date)
    duration_months: Mapped[int]
    message: Mapped[str] = mapped_column(Text)
    owner_reply: Mapped[str] = mapped_column(Text, default="")
    viewing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="open")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
