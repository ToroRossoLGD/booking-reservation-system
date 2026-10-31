from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ViewingReminderPreference(Base):
    __tablename__ = "viewing_reminder_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class ViewingReminderDelivery(Base):
    __tablename__ = "viewing_reminder_deliveries"
    __table_args__ = (
        Index("ix_viewing_reminder_history", "user_id", "created_at", "id"),
        CheckConstraint(
            "(rental_id IS NULL) <> (sale_id IS NULL)", name="ck_viewing_reminder_kind"
        ),
        UniqueConstraint(
            "rental_id", "user_id", "viewing_at", name="uq_rental_reminder_delivery"
        ),
        UniqueConstraint(
            "sale_id", "user_id", "viewing_at", name="uq_sale_reminder_delivery"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    rental_id: Mapped[int | None] = mapped_column(ForeignKey("rental_inquiries.id"))
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sale_inquiries.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    viewing_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
