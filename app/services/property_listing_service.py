from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property_listing import PropertyListing
from app.models.stay import Stay
from app.models.user import User
from app.repositories.property_listing_repository import PropertyListingRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.property_listing import PropertyListingPage, PropertyListingWrite


class PropertyListingService:
    def __init__(self, db: AsyncSession):
        self.repository = PropertyListingRepository(db)
        self.venues = VenueRepository(db)

    async def authorize_venue(self, venue_id: int, user: User):
        venue = await self.venues.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(404, "Venue not found")
        if user.role != "admin" and venue.owner_id != user.id:
            raise HTTPException(403, "You can manage listings only for your own venues")

    async def create(self, data: PropertyListingWrite, user: User):
        await self.authorize_venue(data.venue_id, user)
        if data.booking_enabled and await self.repository.has_hourly_resources(
            data.venue_id
        ):
            raise HTTPException(
                409,
                "Nightly stays require a venue without hourly resources",
            )
        return await self.repository.save(PropertyListing(**data.model_dump()))

    async def update(self, listing_id: int, data: PropertyListingWrite, user: User):
        listing = await self.repository.get(listing_id, lock=True)
        if listing is None:
            raise HTTPException(404, "Listing not found")
        await self.authorize_venue(listing.venue_id, user)
        await self.authorize_venue(data.venue_id, user)
        if data.booking_enabled and await self.repository.has_hourly_resources(
            data.venue_id
        ):
            raise HTTPException(
                409,
                "Nightly stays require a venue without hourly resources",
            )
        if listing.venue_id != data.venue_id:
            existing = await self.repository.db.scalar(
                select(Stay.id).where(Stay.property_id == listing.id).limit(1)
            )
            if existing is not None:
                raise HTTPException(
                    409, "A listing with reservation history cannot change its venue"
                )
        for field, value in data.model_dump().items():
            setattr(listing, field, value)
        return await self.repository.save(listing)

    async def get_public(self, listing_id: int):
        listing = await self.repository.get(listing_id)
        if listing is None or not listing.is_published:
            raise HTTPException(404, "Listing not found")
        return listing

    async def search(
        self, *, city="", offer_type=None, owner_id=None, limit=20, offset=0, **filters
    ):
        items, total = await self.repository.search(
            **filters,
            city=city.strip(),
            offer_type=offer_type,
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )
        return PropertyListingPage(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total,
        )
