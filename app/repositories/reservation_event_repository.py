from inspect import isawaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation_event import ReservationEvent


class ReservationEventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, event: ReservationEvent) -> ReservationEvent:
        add_result = self.db.add(event)
        if isawaitable(add_result):
            await add_result
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_for_reservation(self, reservation_id: int) -> list[ReservationEvent]:
        result = await self.db.execute(
            select(ReservationEvent)
            .where(ReservationEvent.reservation_id == reservation_id)
            .order_by(ReservationEvent.occurred_at, ReservationEvent.id)
        )
        return list(result.scalars().all())
