from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OccupancyFeed(Base):
    __tablename__ = "occupancy_feeds"

    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("property_listings.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
