from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property_listing import PropertyListing
from app.models.resource import Resource
from app.models.stay import Stay
from app.models.stay_block import StayBlock
from app.models.venue import Venue
from app.repositories.preparation_gap import ShiftDays, venue_gap
from app.repositories.seasonal_price_expression import StayTotal


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
        property_type=None,
        neighborhood=None,
        floor=None,
        heating=None,
        furnishing=None,
        has_elevator=None,
        has_parking=None,
        has_terrace=None,
    ):
        filters = []
        for field, value in (
            ("property_type", property_type),
            ("floor", floor),
            ("heating", heating),
            ("furnishing", furnishing),
            ("has_elevator", has_elevator),
            ("has_parking", has_parking),
            ("has_terrace", has_terrace),
        ):
            if value is not None:
                filters.append(getattr(PropertyListing, field) == value)
        if neighborhood and neighborhood.strip():
            filters.append(
                PropertyListing.neighborhood.icontains(
                    neighborhood.strip(), autoescape=True
                )
            )
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
                    PropertyListing.maximum_nights >= (check_out - check_in).days,
                    ~select(Stay.id)
                    .where(
                        Stay.venue_id == PropertyListing.venue_id,
                        Stay.status == "confirmed",
                        ShiftDays(Stay.check_in, -venue_gap(PropertyListing.venue_id))
                        < check_out,
                        ShiftDays(Stay.check_out, venue_gap(PropertyListing.venue_id))
                        > check_in,
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
                eligible.append(
                    and_(
                        PropertyListing.timezone == timezone,
                        PropertyListing.advance_notice_days <= (check_in - today).days,
                        PropertyListing.booking_window_days >= (check_out - today).days,
                    )
                )
            filters.append(or_(*eligible) if eligible else PropertyListing.id < 0)
        price = PropertyListing.price_cents
        if check_in is not None:
            nights = (check_out - check_in).days
            price = StayTotal(
                PropertyListing.seasonal_rates,
                PropertyListing.price_cents,
                check_in,
                check_out,
            )
            # Price filters remain per night: compare exact totals to bounds * nights.
            min_price_cents = (
                None if min_price_cents is None else min_price_cents * nights
            )
            max_price_cents = (
                None if max_price_cents is None else max_price_cents * nights
            )
        for column, lower, upper in (
            (price, min_price_cents, max_price_cents),
            (PropertyListing.area_sqm, min_area_sqm, max_area_sqm),
        ):
            if lower is not None:
                filters.append(column >= lower)
            if upper is not None:
                filters.append(column <= upper)
        ordering = {
            "newest": PropertyListing.id.desc(),
            "price_asc": price.asc(),
            "price_desc": price.desc(),
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
