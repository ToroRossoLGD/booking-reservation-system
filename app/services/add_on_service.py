from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation_add_on import AddOn
from app.models.user import User
from app.repositories.add_on_repository import AddOnRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.add_on import AddOnCreate, AddOnUpdate


class AddOnService:
    def __init__(self, db: AsyncSession):
        self.repository = AddOnRepository(db)
        self.venue_repository = VenueRepository(db)

    async def _ensure_access(self, venue_id: int, user: User) -> None:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if user.role != "admin" and venue.owner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can manage add-ons only for your own venues",
            )

    async def create(self, venue_id: int, data: AddOnCreate, user: User) -> AddOn:
        await self._ensure_access(venue_id, user)
        return await self.repository.create(
            AddOn(venue_id=venue_id, **data.model_dump())
        )

    async def list_public(self, venue_id: int) -> list[AddOn]:
        if await self.venue_repository.get_by_id(venue_id) is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        return await self.repository.list_for_venue(venue_id, active_only=True)

    async def list_managed(self, venue_id: int, user: User) -> list[AddOn]:
        await self._ensure_access(venue_id, user)
        return await self.repository.list_for_venue(venue_id, active_only=False)

    async def update(self, add_on_id: int, data: AddOnUpdate, user: User) -> AddOn:
        add_on = await self.repository.get_by_id(add_on_id)
        if add_on is None:
            raise HTTPException(status_code=404, detail="Add-on not found")
        await self._ensure_access(add_on.venue_id, user)
        for name, value in data.model_dump(exclude_unset=True).items():
            setattr(add_on, name, value)
        return await self.repository.update(add_on)
