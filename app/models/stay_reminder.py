from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StayReminderPreference(Base):
    __tablename__ = "stay_reminder_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class StayReminderDelivery(Base):
    __tablename__ = "stay_reminder_deliveries"
    __table_args__ = (
        Index("ix_stay_reminder_history", "user_id", "created_at", "id"),
        UniqueConstraint(
            "stay_id", "user_id", "kind", "event_date", name="uq_stay_reminder_delivery"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    stay_id: Mapped[int] = mapped_column(ForeignKey("stays.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(16))
    event_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
