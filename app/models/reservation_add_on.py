from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AddOn(Base):
    __tablename__ = "add_ons"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_add_ons_price_nonnegative"),
        CheckConstraint("stock >= 1", name="ck_add_ons_stock_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ReservationAddOn(Base):
    __tablename__ = "reservation_add_ons"
    __table_args__ = (
        CheckConstraint(
            "quantity >= 1", name="ck_reservation_add_ons_quantity_positive"
        ),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_reservation_add_ons_price_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), index=True
    )
    add_on_id: Mapped[int] = mapped_column(ForeignKey("add_ons.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    reservation = relationship("Reservation", back_populates="add_ons")
    add_on = relationship("AddOn")
