from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint(
            "free_cancellation_hours BETWEEN 0 AND 720",
            name="ck_venues_free_cancellation_hours",
        ),
        CheckConstraint(
            "late_cancellation_refund_percent BETWEEN 0 AND 100",
            name="ck_venues_late_refund_percent",
        ),
        CheckConstraint(
            "minimum_booking_notice_minutes BETWEEN 0 AND 10080",
            name="ck_venues_minimum_booking_notice_minutes",
        ),
        CheckConstraint(
            "maximum_advance_booking_days BETWEEN 1 AND 730",
            name="ck_venues_maximum_advance_booking_days",
        ),
        CheckConstraint(
            "minimum_booking_duration_minutes BETWEEN 15 AND 1440",
            name="ck_venues_minimum_booking_duration_minutes",
        ),
        CheckConstraint(
            "maximum_booking_duration_minutes BETWEEN 15 AND 10080",
            name="ck_venues_maximum_booking_duration_minutes",
        ),
        CheckConstraint(
            "maximum_booking_duration_minutes >= minimum_booking_duration_minutes",
            name="ck_venues_booking_duration_range",
        ),
        CheckConstraint(
            "max_active_reservations_per_customer BETWEEN 1 AND 100",
            name="ck_venues_max_active_reservations_per_customer",
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_venues_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_venues_longitude"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    free_cancellation_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24
    )
    late_cancellation_refund_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50
    )
    minimum_booking_notice_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    maximum_advance_booking_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=365
    )
    minimum_booking_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    maximum_booking_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=480
    )
    max_active_reservations_per_customer: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )

    owner = relationship("User", back_populates="venues")
    resources = relationship(
        "Resource",
        back_populates="venue",
        cascade="all, delete-orphan",
    )
