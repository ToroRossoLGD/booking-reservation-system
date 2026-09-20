from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PropertyListing(Base):
    __tablename__ = "property_listings"
    __table_args__ = (
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
    currency: Mapped[str] = mapped_column(String(3))
    contact_email: Mapped[str] = mapped_column(String(254))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
