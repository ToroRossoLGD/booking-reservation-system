import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReservationEventType(str, enum.Enum):
    CREATED = "created"
    RESCHEDULED = "rescheduled"
    CONFIRMED = "confirmed"
    PAID = "paid"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    EXPIRED = "expired"
    REMINDER_SENT = "reminder_sent"


class ReservationEvent(Base):
    __tablename__ = "reservation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    reservation = relationship("Reservation", back_populates="events")
    actor = relationship("User")
