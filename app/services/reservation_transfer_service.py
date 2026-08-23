import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.reservation import ReservationStatus
from app.models.reservation_event import ReservationEvent, ReservationEventType
from app.models.reservation_transfer import (
    ReservationTransfer,
    ReservationTransferStatus,
)
from app.models.user import User
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.reservation_transfer_repository import (
    ReservationTransferRepository,
)
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.reservation_transfer import ReservationTransferCreate
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService


class ReservationTransferService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ReservationTransferRepository(db)
        self.reservation_repository = ReservationRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.venue_repository = VenueRepository(db)
        self.email_service = EmailService()
        self.notification_service = NotificationService(db)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def _owned_reservation(self, reservation_id: int, user: User):
        reservation = await self.reservation_repository.get_by_id(reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        if reservation.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can transfer only your own reservation",
            )
        return reservation

    @staticmethod
    def _ensure_transferable(reservation, current_time: datetime) -> None:
        if reservation.status != ReservationStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=409,
                detail="Only confirmed reservations can be transferred",
            )
        if reservation.start_time <= current_time:
            raise HTTPException(
                status_code=409,
                detail="A reservation cannot be transferred after it starts",
            )

    async def create(
        self,
        reservation_id: int,
        data: ReservationTransferCreate,
        user: User,
        background_tasks: BackgroundTasks,
    ) -> ReservationTransfer:
        reservation = await self._owned_reservation(reservation_id, user)
        now = datetime.now(UTC)
        self._ensure_transferable(reservation, now)
        email = str(data.recipient_email).lower()
        if email == user.email.lower():
            raise HTTPException(
                status_code=400,
                detail="A reservation cannot be transferred to yourself",
            )
        await self.repository.expire_pending(reservation_id, now)
        token = secrets.token_urlsafe(32)
        transfer = ReservationTransfer(
            reservation_id=reservation_id,
            previous_owner_id=user.id,
            recipient_email=email,
            status=ReservationTransferStatus.PENDING.value,
            token_hash=self._hash_token(token),
            active_key=str(reservation_id),
            message=data.message,
            created_at=now,
            expires_at=now
            + timedelta(hours=settings.RESERVATION_TRANSFER_EXPIRE_HOURS),
        )
        try:
            transfer = await self.repository.create(transfer)
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="This reservation already has a pending transfer",
            ) from exc
        background_tasks.add_task(
            self.email_service.send_email,
            email,
            f"Reservation #{reservation_id} transfer invitation",
            f"A reservation has been offered to you.\n\n"
            f"Use this one-time token while signed in as {email}: {token}\n"
            f"It expires at {transfer.expires_at.isoformat()}.",
        )
        return transfer

    async def list_for_reservation(
        self, reservation_id: int, user: User
    ) -> list[ReservationTransfer]:
        reservation = await self.reservation_repository.get_by_id(reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        if reservation.user_id == user.id:
            await self.repository.expire_pending(reservation_id, datetime.now(UTC))
        transfers = await self.repository.list_for_reservation(reservation_id)
        if reservation.user_id == user.id:
            return transfers
        own_transfers = [
            item for item in transfers if item.previous_owner_id == user.id
        ]
        if not own_transfers:
            raise HTTPException(
                status_code=403,
                detail="You cannot view transfers for this reservation",
            )
        return own_transfers

    async def accept(
        self,
        token: str,
        user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict:
        now = datetime.now(UTC)
        transfer = await self.repository.get_by_hash_for_update(self._hash_token(token))
        if transfer is None:
            raise HTTPException(status_code=404, detail="Transfer invitation not found")
        if transfer.status != ReservationTransferStatus.PENDING.value:
            raise HTTPException(
                status_code=409, detail="Transfer invitation is no longer pending"
            )
        if transfer.expires_at <= now:
            transfer.status = ReservationTransferStatus.EXPIRED.value
            transfer.responded_at = now
            transfer.active_key = None
            await self.repository.save(transfer)
            raise HTTPException(
                status_code=410, detail="Transfer invitation has expired"
            )
        if user.email.lower() != transfer.recipient_email:
            await self.db.rollback()
            raise HTTPException(
                status_code=403,
                detail="This transfer invitation belongs to another account",
            )
        await self.reservation_repository.lock_user_for_booking_rules(user.id)
        reservation = await self.reservation_repository.get_by_id_for_update(
            transfer.reservation_id
        )
        if reservation is None:
            await self.db.rollback()
            raise HTTPException(status_code=404, detail="Reservation not found")
        if reservation.user_id != transfer.previous_owner_id:
            await self.db.rollback()
            raise HTTPException(
                status_code=409, detail="Reservation ownership has already changed"
            )
        if reservation.status != ReservationStatus.CONFIRMED.value:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Only confirmed reservations can be transferred",
            )
        if reservation.start_time <= now:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="A reservation cannot be transferred after it starts",
            )
        resource = await self.resource_repository.get_by_id(reservation.resource_id)
        venue = (
            await self.venue_repository.get_by_id(resource.venue_id)
            if resource is not None
            else None
        )
        if resource is None or venue is None:
            await self.db.rollback()
            raise HTTPException(status_code=404, detail="Reservation venue not found")
        active_count = await self.reservation_repository.count_active_for_user_at_venue(
            user.id, venue.id, now
        )
        if active_count >= venue.max_active_reservations_per_customer:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail=("Recipient has reached this venue's active reservation limit"),
            )
        previous_owner_id = reservation.user_id
        reservation.user_id = user.id
        transfer.recipient_user_id = user.id
        transfer.status = ReservationTransferStatus.ACCEPTED.value
        transfer.responded_at = now
        transfer.active_key = None
        event = ReservationEvent(
            reservation_id=reservation.id,
            event_type=ReservationEventType.TRANSFERRED.value,
            actor_id=user.id,
            actor_role=user.role,
            previous_status=reservation.status,
            new_status=reservation.status,
            details={
                "transfer_id": transfer.id,
                "previous_owner_id": previous_owner_id,
                "new_owner_id": user.id,
            },
        )
        transfer = await self.repository.complete(transfer, reservation, event)
        await self.notification_service.create_notification(
            user_id=user.id,
            title="Reservation transfer accepted",
            message=f"Reservation #{reservation.id} now belongs to you.",
            user_email=user.email,
            background_tasks=background_tasks,
        )
        return {
            "transfer": transfer,
            "reservation_id": reservation.id,
            "previous_owner_id": previous_owner_id,
            "new_owner_id": user.id,
        }

    async def decline(self, token: str, user: User) -> ReservationTransfer:
        now = datetime.now(UTC)
        transfer = await self.repository.get_by_hash_for_update(self._hash_token(token))
        if transfer is None:
            raise HTTPException(status_code=404, detail="Transfer invitation not found")
        if transfer.status != ReservationTransferStatus.PENDING.value:
            raise HTTPException(
                status_code=409, detail="Transfer invitation is no longer pending"
            )
        if user.email.lower() != transfer.recipient_email:
            await self.db.rollback()
            raise HTTPException(
                status_code=403,
                detail="This transfer invitation belongs to another account",
            )
        transfer.status = (
            ReservationTransferStatus.EXPIRED.value
            if transfer.expires_at <= now
            else ReservationTransferStatus.DECLINED.value
        )
        transfer.responded_at = now
        transfer.recipient_user_id = user.id
        transfer.active_key = None
        saved = await self.repository.save(transfer)
        if saved.status == ReservationTransferStatus.EXPIRED.value:
            raise HTTPException(
                status_code=410, detail="Transfer invitation has expired"
            )
        return saved

    async def revoke(self, transfer_id: int, user: User) -> ReservationTransfer:
        transfer = await self.repository.get_by_id(transfer_id)
        if transfer is None:
            raise HTTPException(status_code=404, detail="Transfer invitation not found")
        await self._owned_reservation(transfer.reservation_id, user)
        if transfer.status != ReservationTransferStatus.PENDING.value:
            raise HTTPException(
                status_code=409, detail="Only pending transfers can be revoked"
            )
        transfer.status = ReservationTransferStatus.REVOKED.value
        transfer.responded_at = datetime.now(UTC)
        transfer.active_key = None
        return await self.repository.save(transfer)
