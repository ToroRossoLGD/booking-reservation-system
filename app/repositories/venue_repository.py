from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue


class VenueRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, venue: Venue) -> Venue:
        self.db.add(venue)
        await self.db.commit()
        await self.db.refresh(venue)
        return venue

    async def get_all(self) -> list[Venue]:
        result = await self.db.execute(select(Venue).order_by(Venue.id))
        return list(result.scalars().all())

    async def get_by_id(self, venue_id: int) -> Venue | None:
        result = await self.db.execute(select(Venue).where(Venue.id == venue_id))
        return result.scalar_one_or_none()

    async def get_by_owner_id(
        self,
        owner_id: int,
    ) -> list[Venue]:
        result = await self.db.execute(
            select(Venue).where(Venue.owner_id == owner_id).order_by(Venue.id)
        )

        return list(result.scalars().all())
