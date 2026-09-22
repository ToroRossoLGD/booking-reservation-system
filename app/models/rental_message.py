from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RentalMessage(Base):
    __tablename__ = "rental_messages"
    __table_args__ = (
        UniqueConstraint(
            "inquiry_id", "sender_id", "request_id", name="uq_rental_message_request"
        ),
        Index("ix_rental_messages_inquiry_id_id", "inquiry_id", "id"),
        CheckConstraint(
            "kind IN ('message', 'legacy_reply', 'propose', 'confirm', "
            "'decline', 'close', 'withdraw')",
            name="ck_rental_message_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(
        ForeignKey("rental_inquiries.id", ondelete="CASCADE")
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(20), default="message")
    body: Mapped[str] = mapped_column(Text)
    viewing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The timestamp of a legacy owner's last reply was never stored.
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
