from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.config import settings
from app.models.occupancy_source import OccupancySource, OccupancySourceBlock
from app.models.stay_block import StayBlock
from app.services.stay_block_service import StayBlockService


class OccupancySourceService(StayBlockService):
    async def get(self, venue_id, source_id):
        source = await self.db.scalar(
            select(OccupancySource)
            .where(
                OccupancySource.id == source_id,
                OccupancySource.venue_id == venue_id,
            )
            .execution_options(populate_existing=True)
        )
        if source is None:
            raise HTTPException(404, "Calendar source not found")
        return source

    async def blocks(self, source_id):
        result = await self.db.scalars(
            select(StayBlock)
            .join(OccupancySourceBlock, OccupancySourceBlock.block_id == StayBlock.id)
            .where(
                OccupancySourceBlock.source_id == source_id, StayBlock.active.is_(True)
            )
        )
        return list(result.all())

    async def list(self, property_id, user):
        listing = await self.authorize(property_id, user)
        rows = await self.db.scalars(
            select(OccupancySource)
            .where(OccupancySource.venue_id == listing.venue_id)
            .order_by(OccupancySource.id)
        )
        return list(rows.all())

    async def create(self, property_id, user, name):
        if settings.DEMO_MODE:
            raise HTTPException(403, "Calendar sources are disabled in demo mode")
        listing = await self.authorize(property_id, user, lock=True)
        if listing.offer_type != "short_stay":
            raise HTTPException(400, "Only short stays support calendar sources")
        sources = await self.list(property_id, user)
        for source in sources:
            if source.name == name:
                return source
        if len(sources) >= 10:
            raise HTTPException(400, "At most 10 calendar sources per apartment")
        source = OccupancySource(venue_id=listing.venue_id, name=name, revision=0)
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def remove(self, property_id, user, source_id):
        if settings.DEMO_MODE:
            raise HTTPException(403, "Calendar sources are disabled in demo mode")
        listing = await self.authorize(property_id, user, lock=True)
        source = await self.get(listing.venue_id, source_id)
        for block in await self.blocks(source.id):
            block.active = False
        await self.db.execute(
            delete(OccupancySourceBlock).where(
                OccupancySourceBlock.source_id == source.id
            )
        )
        await self.db.execute(
            delete(OccupancySource).where(OccupancySource.id == source.id)
        )
        await self.db.commit()
