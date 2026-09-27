from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PropertyView(Base):
    __tablename__ = "property_views"
    __table_args__ = (
        UniqueConstraint(
            "property_id", "viewed_on", "visitor_hash", name="uq_property_view_daily"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id"), index=True
    )
    viewed_on: Mapped[date] = mapped_column(Date, index=True)
    visitor_hash: Mapped[str] = mapped_column(String(64))
