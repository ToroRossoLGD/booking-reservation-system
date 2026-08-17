import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    EXPIRED = "expired"


class AttendanceStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CHECKED_IN = "checked_in"
    NO_SHOW = "no_show"


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_reservations_user_idempotency_key",
        ),
    )

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

    attendance_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AttendanceStatus.SCHEDULED.value,
        index=True,
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    no_show_marked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    recurrence_series_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_request_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
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
    events = relationship(
        "ReservationEvent",
        back_populates="reservation",
        cascade="all, delete-orphan",
        order_by="ReservationEvent.occurred_at",
    )
