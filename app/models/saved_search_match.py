from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedSearchMatch(Base):
    __tablename__ = "saved_search_matches"

    search_id: Mapped[int] = mapped_column(
        ForeignKey("saved_searches.id", ondelete="CASCADE"), primary_key=True
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id", ondelete="CASCADE"), primary_key=True
    )
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
