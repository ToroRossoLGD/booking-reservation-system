from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PropertyReview(Base):
    __tablename__ = "property_reviews"
    __table_args__ = (
        UniqueConstraint("stay_id", name="uq_property_review_stay"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_property_review_rating"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    stay_id: Mapped[int] = mapped_column(ForeignKey("stays.id"))
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id"), index=True
    )
    rating: Mapped[int]
    comment: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
