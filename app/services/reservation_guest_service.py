import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.reservation import ReservationStatus
from app.models.reservation_guest import (
    GuestInvitationStatus,
    ReservationGuestInvitation,
)
from app.models.user import User
from app.repositories.reservation_guest_repository import ReservationGuestRepository
from app.repositories.reservation_repository import ReservationRepository
from app.schemas.reservation_guest import GuestInvitationCreate
from app.services.email_service import EmailService


class ReservationGuestService:
    def __init__(self, db: AsyncSession):
        self.repository = ReservationGuestRepository(db)
        self.reservation_repository = ReservationRepository(db)
        self.email_service = EmailService()
        self.db = db

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def _owned_reservation(self, reservation_id: int, user: User):
        reservation = await self.reservation_repository.get_by_id(reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        if reservation.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can manage guests only for your own reservations",
            )
        return reservation

    async def invite(
        self,
        reservation_id: int,
        data: GuestInvitationCreate,
        current_user: User,
        background_tasks: BackgroundTasks,
    ) -> ReservationGuestInvitation:
        reservation = await self._owned_reservation(reservation_id, current_user)
        if reservation.status not in {
            ReservationStatus.PENDING.value,
            ReservationStatus.CONFIRMED.value,
        }:
            raise HTTPException(
                status_code=409,
                detail="Guests can be invited only to active reservations",
            )

        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        invitation = ReservationGuestInvitation(
            reservation_id=reservation.id,
            email=str(data.email).lower(),
            guest_name=data.guest_name.strip(),
            status=GuestInvitationStatus.PENDING.value,
            token_hash=self._hash_token(token),
            invited_at=now,
            expires_at=now + timedelta(hours=settings.GUEST_INVITATION_EXPIRE_HOURS),
        )
        try:
            invitation = await self.repository.create(invitation)
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="This email has already been invited to the reservation",
            ) from exc

        background_tasks.add_task(
            self.email_service.send_email,
            invitation.email,
            f"Invitation to reservation #{reservation.id}",
            f"Hello {invitation.guest_name},\n\n"
            f"Use this invitation token to accept or decline: {token}\n"
            f"It expires at {invitation.expires_at.isoformat()}.",
        )
        return invitation

    async def list_for_reservation(
        self, reservation_id: int, current_user: User
    ) -> list[ReservationGuestInvitation]:
        await self._owned_reservation(reservation_id, current_user)
        return await self.repository.get_for_reservation(reservation_id)

    async def respond(self, token: str, response: str) -> ReservationGuestInvitation:
        token_hash = self._hash_token(token)
        invitation = await self.repository.get_by_hash(token_hash)
        if invitation is None:
            raise HTTPException(status_code=404, detail="Invitation not found")
        if invitation.status != GuestInvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=409, detail="Invitation is no longer pending"
            )
        if invitation.expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=410, detail="Invitation has expired")
        updated = await self.repository.respond_if_pending(
            token_hash, response, datetime.now(UTC)
        )
        if updated is None:
            raise HTTPException(
                status_code=409, detail="Invitation is no longer pending"
            )
        return updated

    async def revoke(
        self, invitation_id: int, current_user: User
    ) -> ReservationGuestInvitation:
        invitation = await self.repository.get_by_id(invitation_id)
        if invitation is None:
            raise HTTPException(status_code=404, detail="Invitation not found")
        await self._owned_reservation(invitation.reservation_id, current_user)
        if invitation.status != GuestInvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=409, detail="Only pending invitations can be revoked"
            )
        invitation.status = GuestInvitationStatus.REVOKED.value
        invitation.responded_at = datetime.now(UTC)
        return await self.repository.update(invitation)
