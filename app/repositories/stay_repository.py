from sqlalchemy import and_, false, func, or_, select
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

    async def owner_overview(
        self,
        user_id,
        today,
        property_id=None,
        status=None,
        day=None,
        offset=0,
        limit=20,
    ):
        owned = select(Stay).join(Venue).where(Venue.owner_id == user_id)
        options = await self.db.execute(
            select(PropertyListing.id, PropertyListing.title)
            .join(Stay, Stay.property_id == PropertyListing.id)
            .join(Venue, Stay.venue_id == Venue.id)
            .where(Venue.owner_id == user_id)
            .distinct()
            .order_by(PropertyListing.title, PropertyListing.id)
        )
        if property_id is not None:
            owned = owned.where(Stay.property_id == property_id)
        zones = await self.db.scalars(owned.with_only_columns(Stay.timezone).distinct())
        dates = {zone: today(zone) for zone in zones.all()}

        def today_filter(column):
            return or_(
                false(),
                *(
                    and_(Stay.timezone == zone, column == date)
                    for zone, date in dates.items()
                ),
            )

        async def count(query):
            return (
                await self.db.scalar(select(func.count()).select_from(query.subquery()))
                or 0
            )

        confirmed = owned.where(Stay.status == "confirmed")
        arrivals = await count(confirmed.where(today_filter(Stay.check_in)))
        departures = await count(confirmed.where(today_filter(Stay.check_out)))
        filtered = owned
        if status:
            filtered = filtered.where(Stay.status == status)
        if day:
            filtered = filtered.where(
                Stay.status == "confirmed",
                today_filter(Stay.check_in if day == "arrivals" else Stay.check_out),
            )
        total = await count(filtered)
        ordering = (Stay.check_in.desc(), Stay.id.desc())
        if day:
            clock = Stay.check_in_time if day == "arrivals" else Stay.check_out_time
            ordering = (clock.asc().nulls_last(), Stay.id.asc())
        items = await self.db.scalars(
            filtered.order_by(*ordering).offset(offset).limit(limit)
        )
        return dict(
            items=list(items.all()),
            total=total,
            has_next=offset + limit < total,
            arrivals_today=arrivals,
            departures_today=departures,
            properties=[dict(id=id, title=title) for id, title in options.all()],
        )
