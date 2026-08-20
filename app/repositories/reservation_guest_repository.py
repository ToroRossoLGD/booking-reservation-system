from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation_guest import ReservationGuestInvitation


class ReservationGuestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, invitation: ReservationGuestInvitation
    ) -> ReservationGuestInvitation:
        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)
        return invitation

    async def get_by_hash(self, token_hash: str) -> ReservationGuestInvitation | None:
        result = await self.db.execute(
            select(ReservationGuestInvitation).where(
                ReservationGuestInvitation.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, invitation_id: int) -> ReservationGuestInvitation | None:
        result = await self.db.execute(
            select(ReservationGuestInvitation).where(
                ReservationGuestInvitation.id == invitation_id
            )
        )
        return result.scalar_one_or_none()

    async def get_for_reservation(
        self, reservation_id: int
    ) -> list[ReservationGuestInvitation]:
        result = await self.db.execute(
            select(ReservationGuestInvitation)
            .where(ReservationGuestInvitation.reservation_id == reservation_id)
            .order_by(ReservationGuestInvitation.invited_at)
        )
        return list(result.scalars().all())

    async def update(
        self, invitation: ReservationGuestInvitation
    ) -> ReservationGuestInvitation:
        await self.db.commit()
        await self.db.refresh(invitation)
        return invitation

    async def respond_if_pending(
        self, token_hash: str, response: str, responded_at: datetime
    ) -> ReservationGuestInvitation | None:
        result = await self.db.execute(
            update(ReservationGuestInvitation)
            .where(
                ReservationGuestInvitation.token_hash == token_hash,
                ReservationGuestInvitation.status == "pending",
                ReservationGuestInvitation.expires_at > responded_at,
            )
            .values(status=response, responded_at=responded_at)
            .returning(ReservationGuestInvitation)
        )
        invitation = result.scalar_one_or_none()
        if invitation is not None:
            await self.db.commit()
        else:
            await self.db.rollback()
        return invitation
