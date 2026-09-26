from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property_listing import PropertyListing
from app.models.resource import Resource
from app.models.stay import Stay
from app.models.stay_block import StayBlock
from app.models.venue import Venue


class PropertyListingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, listing_id: int, lock=False) -> PropertyListing | None:
        query = select(PropertyListing).where(PropertyListing.id == listing_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.db.scalar(query)

    async def save(self, listing: PropertyListing) -> PropertyListing:
        self.db.add(listing)
        await self.db.commit()
        await self.db.refresh(listing)
        return listing

    async def has_hourly_resources(self, venue_id):
        await self.db.scalar(
            select(Venue.id).where(Venue.id == venue_id).with_for_update()
        )
        return (
            await self.db.scalar(
                select(Resource.id).where(Resource.venue_id == venue_id).limit(1)
            )
            is not None
        )

    async def search(
        self,
        *,
        city="",
        offer_type=None,
        owner_id=None,
        limit=20,
        offset=0,
        currency=None,
        min_price_cents=None,
        max_price_cents=None,
        min_area_sqm=None,
        max_area_sqm=None,
        rooms=None,
        sort="newest",
        check_in=None,
        check_out=None,
        guests=None,
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
        if currency is not None:
            filters.append(PropertyListing.currency == currency)
        if rooms is not None:
            filters.append(PropertyListing.rooms == rooms)
        if check_in is not None:
            filters.extend(
                [
                    PropertyListing.offer_type == "short_stay",
                    PropertyListing.booking_enabled.is_(True),
                    ~select(StayBlock.id)
                    .where(
                        StayBlock.venue_id == PropertyListing.venue_id,
                        StayBlock.active.is_(True),
                        StayBlock.check_in < check_out,
                        StayBlock.check_out > check_in,
                    )
                    .exists(),
                    PropertyListing.max_guests >= guests,
                    PropertyListing.minimum_nights <= (check_out - check_in).days,
                    ~select(Stay.id)
                    .where(
                        Stay.venue_id == PropertyListing.venue_id,
                        Stay.status == "confirmed",
                        Stay.check_in < check_out,
                        Stay.check_out > check_in,
                    )
                    .exists(),
                ]
            )
            # Filter before counting/pagination, using each property's local date.
            # One timezone query, never one availability query per listing.
            timezones = await self.db.scalars(
                select(PropertyListing.timezone).join(Venue).where(*filters).distinct()
            )
            now = datetime.now(UTC)
            eligible = []
            for timezone in timezones:
                today = now.astimezone(ZoneInfo(timezone)).date()
                if today + timedelta(
                    days=1
                ) <= check_in and check_out <= today + timedelta(days=365):
                    eligible.append(timezone)
            filters.append(PropertyListing.timezone.in_(eligible))
        for column, lower, upper in (
            (PropertyListing.price_cents, min_price_cents, max_price_cents),
            (PropertyListing.area_sqm, min_area_sqm, max_area_sqm),
        ):
            if lower is not None:
                filters.append(column >= lower)
            if upper is not None:
                filters.append(column <= upper)
        ordering = {
            "newest": PropertyListing.id.desc(),
            "price_asc": PropertyListing.price_cents.asc(),
            "price_desc": PropertyListing.price_cents.desc(),
            "area_desc": PropertyListing.area_sqm.desc(),
        }[sort]
        query = select(PropertyListing).join(Venue).where(*filters)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.scalars(
            query.order_by(ordering, PropertyListing.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all()), total or 0
