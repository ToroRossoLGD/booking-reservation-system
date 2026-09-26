from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property_listing import PropertyListing
from app.models.stay import Stay
from app.models.stay_block import StayBlock
from app.models.user import User
from app.models.venue import Venue


class StayRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def listing(self, property_id, lock=False):
        query = select(PropertyListing).where(PropertyListing.id == property_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.db.scalar(query)

    async def lock_user(self, user_id):
        await self.db.scalar(
            select(User.id).where(User.id == user_id).with_for_update()
        )

    async def lock_venue(self, venue_id):
        return await self.db.scalar(
            select(Venue).where(Venue.id == venue_id).with_for_update()
        )

    async def previous_request(self, user_id, request_id):
        return await self.db.scalar(
            select(Stay).where(
                Stay.user_id == user_id, Stay.request_id == str(request_id)
            )
        )

    async def occupied(self, venue_id, start, end):
        result = await self.db.scalars(
            select(Stay)
            .where(
                Stay.venue_id == venue_id,
                Stay.status == "confirmed",
                Stay.check_in < end,
                Stay.check_out > start,
            )
            .order_by(Stay.check_in)
        )
        blocks = await self.db.scalars(
            select(StayBlock)
            .where(
                StayBlock.venue_id == venue_id,
                StayBlock.active.is_(True),
                StayBlock.check_in < end,
                StayBlock.check_out > start,
            )
            .order_by(StayBlock.check_in)
        )
        return sorted([*result.all(), *blocks.all()], key=lambda item: item.check_in)

    async def save(self, stay):
        self.db.add(stay)
        await self.db.commit()
        await self.db.refresh(stay)
        return stay

    async def get(self, stay_id, lock=False):
        query = select(Stay).where(Stay.id == stay_id)
        if lock:
            query = query.with_for_update()
        return await self.db.scalar(query)

    async def list_for_user(self, user_id, owner=False, offset=0, limit=20):
        query = select(Stay)
        if owner:
            query = query.join(Venue).where(Venue.owner_id == user_id)
        else:
            query = query.where(Stay.user_id == user_id)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.scalars(
            query.order_by(Stay.check_in.desc(), Stay.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all()), total or 0

    async def guest_emails(self, user_ids):
        result = await self.db.execute(
            select(User.id, User.email).where(User.id.in_(user_ids))
        )
        return dict(result.all())
