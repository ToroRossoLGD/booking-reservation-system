from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.stay_block import StayBlock
from app.models.venue import Venue
from app.repositories.stay_repository import StayRepository
from app.schemas.stay_block import StayBlockPage
from app.services.stay_service import StayService


class StayBlockService:
    def __init__(self, db):
        self.db = db
        self.stays = StayRepository(db)

    async def authorize(self, property_id, user, lock=False):
        # Same order as reservation creation: listing, then its shared venue.
        listing = await self.stays.listing(property_id, lock=lock)
        if listing is None:
            raise HTTPException(404, "Property not found")
        venue = (
            await self.stays.lock_venue(listing.venue_id)
            if lock
            else await self.db.scalar(select(Venue).where(Venue.id == listing.venue_id))
        )
        if user.role not in ("owner", "admin") or (
            user.role != "admin" and venue.owner_id != user.id
        ):
            raise HTTPException(403, "You cannot manage this property's availability")
        return listing

    async def create(self, property_id, data, user):
        listing = await self.authorize(property_id, user, lock=True)
        previous = await self.db.scalar(
            select(StayBlock).where(
                StayBlock.venue_id == listing.venue_id,
                StayBlock.request_id == str(data.request_id),
            )
        )
        if previous:
            if (previous.check_in, previous.check_out, previous.reason) != (
                data.check_in,
                data.check_out,
                data.reason,
            ) or not previous.active:
                raise HTTPException(
                    409, "Request identifier already used or block removed"
                )
            return previous
        if listing.offer_type != "short_stay":
            raise HTTPException(400, "Blocks can only be created for short stays")
        today = StayService.today(listing.timezone)
        if data.check_in < today or data.check_out > today + timedelta(days=365):
            raise HTTPException(
                400, "Block must start today or later and end within 365 days"
            )
        if await self.stays.occupied(listing.venue_id, data.check_in, data.check_out):
            raise HTTPException(409, "Dates overlap an existing reservation or block")
        block = StayBlock(
            venue_id=listing.venue_id,
            created_by_id=user.id,
            request_id=str(data.request_id),
            check_in=data.check_in,
            check_out=data.check_out,
            reason=data.reason,
            active=True,
        )
        self.db.add(block)
        await self.db.commit()
        await self.db.refresh(block)
        return block

    async def list(self, property_id, user, offset=0, limit=20):
        listing = await self.authorize(property_id, user)
        query = select(StayBlock).where(
            StayBlock.venue_id == listing.venue_id, StayBlock.active.is_(True)
        )
        total = (
            await self.db.scalar(select(func.count()).select_from(query.subquery()))
            or 0
        )
        items = await self.db.scalars(
            query.order_by(StayBlock.check_in, StayBlock.id).offset(offset).limit(limit)
        )
        return StayBlockPage(
            items=list(items), total=total, has_next=offset + limit < total
        )

    async def remove(self, property_id, block_id, user):
        listing = await self.authorize(property_id, user, lock=True)
        block = await self.db.scalar(
            select(StayBlock)
            .where(StayBlock.id == block_id, StayBlock.venue_id == listing.venue_id)
            .execution_options(populate_existing=True)
        )
        if block is None:
            raise HTTPException(404, "Block not found")
        block.active = False
        await self.db.commit()
