from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation
from app.models.reservation_event import ReservationEvent
from app.models.reservation_transfer import ReservationTransfer
from app.repositories.webhook_repository import WebhookRepository


class ReservationTransferRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, transfer: ReservationTransfer) -> ReservationTransfer:
        self.db.add(transfer)
        await self.db.commit()
        await self.db.refresh(transfer)
        return transfer

    async def get_by_id(self, transfer_id: int) -> ReservationTransfer | None:
        result = await self.db.execute(
            select(ReservationTransfer).where(ReservationTransfer.id == transfer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash_for_update(
        self, token_hash: str
    ) -> ReservationTransfer | None:
        result = await self.db.execute(
            select(ReservationTransfer)
            .where(ReservationTransfer.token_hash == token_hash)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_for_reservation(
        self, reservation_id: int
    ) -> list[ReservationTransfer]:
        result = await self.db.execute(
            select(ReservationTransfer)
            .where(ReservationTransfer.reservation_id == reservation_id)
            .order_by(ReservationTransfer.created_at.desc())
        )
        return list(result.scalars().all())

    async def expire_pending(self, reservation_id: int, current_time: datetime) -> None:
        await self.db.execute(
            update(ReservationTransfer)
            .where(
                ReservationTransfer.reservation_id == reservation_id,
                ReservationTransfer.status == "pending",
                ReservationTransfer.expires_at <= current_time,
            )
            .values(status="expired", responded_at=current_time, active_key=None)
        )
        await self.db.commit()

    async def save(self, transfer: ReservationTransfer) -> ReservationTransfer:
        await self.db.commit()
        await self.db.refresh(transfer)
        return transfer

    async def complete(
        self,
        transfer: ReservationTransfer,
        reservation: Reservation,
        event: ReservationEvent,
    ) -> ReservationTransfer:
        self.db.add(event)
        try:
            await self.db.flush()
            await self.db.refresh(event)
            await WebhookRepository(self.db).enqueue_for_event(event, commit=False)
            await self.db.commit()
            await self.db.refresh(transfer)
            await self.db.refresh(reservation)
        except Exception:
            await self.db.rollback()
            raise
        return transfer
