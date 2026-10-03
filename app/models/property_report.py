from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
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


class PropertyReport(Base):
    __tablename__ = "property_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_property_report_request"),
        CheckConstraint(
            "status IN ('pending', 'dismissed', 'action_taken')",
            name="ck_property_report_status",
        ),
        Index(
            "uq_pending_property_report",
            "user_id",
            "property_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36))
    category: Mapped[str] = mapped_column(String(24))
    details: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PropertyModerationEvent(Base):
    __tablename__ = "property_moderation_events"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "request_id", name="uq_property_moderation_request"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("property_reports.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text)
    version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
