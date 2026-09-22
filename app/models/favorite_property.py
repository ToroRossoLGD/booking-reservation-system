from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FavoriteProperty(Base):
    __tablename__ = "favorite_properties"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "property_id", name="uq_favorite_property_user_property"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
