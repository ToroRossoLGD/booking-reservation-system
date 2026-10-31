from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PropertyEmailDigest(Base):
    __tablename__ = "property_email_digests"
    __table_args__ = (Index("ix_property_email_digest_due", "enabled", "next_run_at"),)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    cursor: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str] = mapped_column(String(24), default="pending")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PropertyEmailDigestItem(Base):
    __tablename__ = "property_email_digest_items"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    # Retain the identifier after inbox dismissal; deliberately no notification FK.
    notification_id: Mapped[int] = mapped_column(primary_key=True)
