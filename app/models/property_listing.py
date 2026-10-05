from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PropertyListing(Base):
    __tablename__ = "property_listings"
    __table_args__ = (
        Index("ix_property_map_location", "map_latitude", "map_longitude"),
        CheckConstraint(
            "(map_latitude IS NULL AND map_longitude IS NULL) OR "
            "(map_latitude IS NOT NULL AND map_longitude IS NOT NULL AND "
            "map_latitude BETWEEN -85 AND 85 AND map_longitude BETWEEN -180 AND 180)",
            name="ck_property_map_location",
        ),
        CheckConstraint(
            "moderation_state IN ('clear', 'suspended', 'appealed')",
            name="ck_property_moderation_state",
        ),
        CheckConstraint(
            "NOT is_published OR moderation_state = 'clear'",
            name="ck_property_moderation_publish",
        ),
        CheckConstraint(
            "offer_type IN ('short_stay', 'long_term', 'sale')",
            name="ck_property_offer",
        ),
        CheckConstraint(
            "price_cents BETWEEN 1 AND 1000000000000", name="ck_property_price"
        ),
        CheckConstraint("area_sqm BETWEEN 1 AND 100000", name="ck_property_area"),
        CheckConstraint("rooms BETWEEN 0 AND 100", name="ck_property_rooms"),
    )

    deposit_cents: Mapped[int | None] = mapped_column(BigInteger)
    map_latitude: Mapped[float | None] = mapped_column(Float)
    map_longitude: Mapped[float | None] = mapped_column(Float)
    moderation_state: Mapped[str] = mapped_column(
        String(16), default="clear", server_default="clear"
    )
    moderation_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    moderation_note: Mapped[str] = mapped_column(Text, default="", server_default="")
    moderation_appeal: Mapped[str] = mapped_column(Text, default="", server_default="")
    monthly_bills_cents: Mapped[int | None] = mapped_column(BigInteger)
    available_from: Mapped[date | None] = mapped_column(Date)
    minimum_rental_months: Mapped[int | None]
    pets_policy: Mapped[str | None] = mapped_column(String(20))

    first_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100), index=True)
    offer_type: Mapped[str] = mapped_column(String(20), index=True)
    area_sqm: Mapped[int] = mapped_column(Integer)
    rooms: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(BigInteger)
    seasonal_rates: Mapped[list] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    currency: Mapped[str] = mapped_column(String(3))
    contact_email: Mapped[str] = mapped_column(String(254))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    booking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    max_guests: Mapped[int] = mapped_column(Integer, default=2)
    minimum_nights: Mapped[int] = mapped_column(Integer, default=1)
    maximum_nights: Mapped[int] = mapped_column(
        Integer, default=90, server_default="90"
    )
    preparation_days: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    advance_notice_days: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    booking_window_days: Mapped[int] = mapped_column(
        Integer, default=365, server_default="365"
    )
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Belgrade")
    property_type: Mapped[str | None] = mapped_column(String(20))
    neighborhood: Mapped[str | None] = mapped_column(String(100))
    floor: Mapped[int | None] = mapped_column(Integer)
    heating: Mapped[str | None] = mapped_column(String(20))
    furnishing: Mapped[str | None] = mapped_column(String(20))
    has_elevator: Mapped[bool | None] = mapped_column(Boolean)
    has_parking: Mapped[bool | None] = mapped_column(Boolean)
    has_terrace: Mapped[bool | None] = mapped_column(Boolean)
    check_in_time: Mapped[str | None] = mapped_column(String(5))
    check_out_time: Mapped[str | None] = mapped_column(String(5))
