from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OccupancyImportRun(Base):
    __tablename__ = "occupancy_import_runs"
    __table_args__ = (
        Index("ix_occupancy_import_runs_venue_id_id", "venue_id", "id"),
        CheckConstraint(
            "status IN ('applied', 'conflict')", name="ck_import_run_status"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    status: Mapped[str] = mapped_column(String(16))
    created: Mapped[int]
    existing: Mapped[int]
    conflicts: Mapped[int]
    ignored: Mapped[int]
    clipped: Mapped[int]
