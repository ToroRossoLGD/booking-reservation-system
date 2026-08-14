import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WaitlistStatus(str, enum.Enum):
    WAITING = "waiting"
    NOTIFIED = "notified"


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        Index(
            "uq_waitlist_entries_waiting_slot",
            "user_id",
            "resource_id",
            "start_time",
            "end_time",
            unique=True,
            postgresql_where=text("status = 'waiting'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id"), nullable=False, index=True
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=WaitlistStatus.WAITING.value, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
