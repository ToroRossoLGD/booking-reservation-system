from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OccupancySync(Base):
    __tablename__ = "occupancy_syncs"
    __table_args__ = (Index("ix_occupancy_sync_due", "enabled", "next_run_at"),)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("occupancy_sources.id"), primary_key=True
    )
    property_id: Mapped[int] = mapped_column(ForeignKey("property_listings.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    encrypted_url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    allow_empty: Mapped[bool] = mapped_column(default=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str] = mapped_column(String(24), default="pending")
