from datetime import UTC, date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyVenueMetric(Base):
    __tablename__ = "daily_venue_metrics"
    __table_args__ = (
        UniqueConstraint("metric_date", "venue_id", name="uq_daily_venue_metric"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    venue_id: Mapped[int] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reservation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_customer_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    booked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    booked_capacity_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cancelled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_show_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reservations_by_status: Mapped[dict] = mapped_column(JSON, nullable=False)
    revenue_by_currency: Mapped[dict] = mapped_column(JSON, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class DailyResourceMetric(Base):
    __tablename__ = "daily_resource_metrics"
    __table_args__ = (
        UniqueConstraint(
            "metric_date", "resource_id", name="uq_daily_resource_metric"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    venue_id: Mapped[int] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reservation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_customer_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    booked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    booked_capacity_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cancelled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_show_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reservations_by_status: Mapped[dict] = mapped_column(JSON, nullable=False)
    revenue_by_currency: Mapped[dict] = mapped_column(JSON, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
