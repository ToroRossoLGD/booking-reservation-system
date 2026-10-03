from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StayDateChange(Base):
    __tablename__ = "stay_date_changes"
    __table_args__ = (
        UniqueConstraint("stay_id", "request_id", name="uq_stay_change_request"),
        CheckConstraint("check_out > check_in", name="ck_stay_change_dates"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'withdrawn', 'expired')",
            name="ck_stay_change_status",
        ),
        Index(
            "uq_stay_pending_change",
            "stay_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stay_id: Mapped[int] = mapped_column(
        ForeignKey("stays.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36))
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    original: Mapped[dict] = mapped_column(JSON)
    quote: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
