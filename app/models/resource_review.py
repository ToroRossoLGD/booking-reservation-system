import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewStatus(str, enum.Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"


class ResourceReview(Base):
    __tablename__ = "resource_reviews"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "resource_id",
            name="uq_resource_review_user_resource",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id"),
        nullable=False,
        index=True,
    )

    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ReviewStatus.VISIBLE.value, index=True
    )
    moderation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    moderated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    moderated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    owner_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
