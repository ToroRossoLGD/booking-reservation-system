from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property_listing import PropertyListing
from app.models.venue import Venue


class PropertyListingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, listing_id: int) -> PropertyListing | None:
        return await self.db.get(PropertyListing, listing_id)

    async def save(self, listing: PropertyListing) -> PropertyListing:
        self.db.add(listing)
        await self.db.commit()
        await self.db.refresh(listing)
        return listing

    async def search(
        self, *, city="", offer_type=None, owner_id=None, limit=20, offset=0
    ):
        filters = []
        if owner_id is None:
            filters.append(PropertyListing.is_published.is_(True))
        else:
            filters.append(Venue.owner_id == owner_id)
        if city:
            filters.append(PropertyListing.city.icontains(city, autoescape=True))
        if offer_type:
            filters.append(PropertyListing.offer_type == offer_type)
        query = select(PropertyListing).join(Venue).where(*filters)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.scalars(
            query.order_by(PropertyListing.id.desc()).limit(limit).offset(offset)
        )
        return list(result.all()), total or 0
