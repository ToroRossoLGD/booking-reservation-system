from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OccupancySource(Base):
    __tablename__ = "occupancy_sources"
    __table_args__ = (
        UniqueConstraint("venue_id", "name", name="uq_occupancy_source_name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(16))


class OccupancySourceBlock(Base):
    __tablename__ = "occupancy_source_blocks"
    source_id: Mapped[int] = mapped_column(
        ForeignKey("occupancy_sources.id"), primary_key=True
    )
    block_id: Mapped[int] = mapped_column(
        ForeignKey("stay_blocks.id"), primary_key=True, unique=True
    )
