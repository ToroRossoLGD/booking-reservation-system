from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation, ReservationStatus
from app.models.reservation_add_on import AddOn, ReservationAddOn


class AddOnRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, add_on: AddOn) -> AddOn:
        self.db.add(add_on)
        await self.db.commit()
        await self.db.refresh(add_on)
        return add_on

    async def get_by_id(self, add_on_id: int, *, lock: bool = False) -> AddOn | None:
        query = select(AddOn).where(AddOn.id == add_on_id)
        if lock:
            query = query.with_for_update()
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_for_venue(self, venue_id: int, active_only: bool) -> list[AddOn]:
        query = select(AddOn).where(AddOn.venue_id == venue_id)
        if active_only:
            query = query.where(AddOn.is_active.is_(True))
        result = await self.db.execute(query.order_by(AddOn.name, AddOn.id))
        return list(result.scalars().all())

    async def update(self, add_on: AddOn) -> AddOn:
        await self.db.commit()
        await self.db.refresh(add_on)
        return add_on

    async def reserved_quantity(
        self,
        add_on_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_reservation_id: int | None = None,
    ) -> int:
        active = or_(
            Reservation.status == ReservationStatus.CONFIRMED.value,
            and_(
                Reservation.status == ReservationStatus.PENDING.value,
                or_(
                    Reservation.hold_expires_at.is_(None),
                    Reservation.hold_expires_at > datetime.now(UTC),
                ),
            ),
        )
        query = (
            select(func.coalesce(func.sum(ReservationAddOn.quantity), 0))
            .join(Reservation, Reservation.id == ReservationAddOn.reservation_id)
            .where(
                ReservationAddOn.add_on_id == add_on_id,
                active,
                Reservation.start_time < end_time,
                Reservation.end_time > start_time,
            )
        )
        if exclude_reservation_id is not None:
            query = query.where(Reservation.id != exclude_reservation_id)
        result = await self.db.execute(query)
        return int(result.scalar_one())
