from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SaleInquiry(Base):
    __tablename__ = "sale_inquiries"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_sale_inquiry_request"),
        CheckConstraint(
            "status IN ('open', 'viewing_proposed', 'viewing_confirmed', "
            "'closed', 'withdrawn')",
            name="ck_sale_inquiry_status",
        ),
        Index(
            "uq_active_sale_inquiry",
            "user_id",
            "property_id",
            unique=True,
            postgresql_where=text("status NOT IN ('closed', 'withdrawn')"),
            sqlite_where=text("status NOT IN ('closed', 'withdrawn')"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.id"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(160))
    asking_price_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    message: Mapped[str] = mapped_column(Text)
    owner_reply: Mapped[str] = mapped_column(Text, default="")
    viewing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="open")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SaleMessage(Base):
    __tablename__ = "sale_messages"
    __table_args__ = (
        UniqueConstraint(
            "inquiry_id", "sender_id", "request_id", name="uq_sale_message_request"
        ),
        Index("ix_sale_messages_inquiry_id_id", "inquiry_id", "id"),
        CheckConstraint(
            "kind IN ('message', 'propose', 'confirm', 'decline', 'close', 'withdraw')",
            name="ck_sale_message_kind",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(
        ForeignKey("sale_inquiries.id", ondelete="CASCADE")
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(20), default="message")
    body: Mapped[str] = mapped_column(Text)
    viewing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
