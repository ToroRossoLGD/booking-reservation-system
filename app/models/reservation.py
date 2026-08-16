import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    EXPIRED = "expired"


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ReservationStatus.PENDING.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    recurrence_series_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    quoted_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quoted_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    base_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_amount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    promotion_id: Mapped[int | None] = mapped_column(
        ForeignKey("promotions.id"), nullable=True, index=True
    )
    promotion_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    promotion_discount_percent: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id"),
        nullable=False,
        index=True,
    )

    user = relationship("User")
    resource = relationship("Resource")
