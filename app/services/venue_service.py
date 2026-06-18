from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.venue import Venue
from app.repositories.venue_repository import VenueRepository
from app.schemas.venue import VenueCreate


class VenueService:
    def __init__(self, db: AsyncSession):
        self.venue_repository = VenueRepository(db)

    async def create_venue(
        self,
        data: VenueCreate,
        current_user: User,
    ) -> Venue:
        venue = Venue(
            name=data.name,
            description=data.description,
            address=data.address,
            owner_id=current_user.id,
        )

        return await self.venue_repository.create(venue)

    async def get_all_venues(self) -> list[Venue]:
        return await self.venue_repository.get_all()

    async def get_venue_by_id(self, venue_id: int) -> Venue:
        venue = await self.venue_repository.get_by_id(venue_id)

        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        return venue
