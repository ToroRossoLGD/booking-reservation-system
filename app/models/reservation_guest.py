import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GuestInvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"


class ReservationGuestInvitation(Base):
    __tablename__ = "reservation_guest_invitations"
    __table_args__ = (
        UniqueConstraint(
            "reservation_id", "email", name="uq_guest_invitation_reservation_email"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    guest_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GuestInvitationStatus.PENDING.value
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
