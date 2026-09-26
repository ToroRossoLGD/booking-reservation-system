from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.models.stay import Stay
from app.repositories.stay_repository import StayRepository
from app.schemas.stay import StayCalendar, StayPage, StayQuote, StayRead


class StayService:
    def __init__(self, db):
        self.repository = StayRepository(db)

    @staticmethod
    def today(timezone):
        return datetime.now(ZoneInfo(timezone)).date()

    async def bookable_listing(self, property_id, lock=False):
        listing = await self.repository.listing(property_id, lock)
        if listing is None or not listing.is_published:
            raise HTTPException(404, "Property not found")
        if listing.offer_type != "short_stay" or not listing.booking_enabled:
            raise HTTPException(
                400, "Online reservations are not enabled for this property"
            )
        return listing

    def validate_dates(self, listing, data):
        today = self.today(listing.timezone)
        if data.check_in < today + timedelta(days=1):
            raise HTTPException(
                400, "Arrival must be tomorrow or later in the property timezone"
            )
        if data.check_out > today + timedelta(days=365):
            raise HTTPException(400, "Departure must be within the next 365 days")
        nights = (data.check_out - data.check_in).days
        if nights < listing.minimum_nights:
            raise HTTPException(400, f"Minimum stay is {listing.minimum_nights} nights")
        if data.guests > listing.max_guests:
            raise HTTPException(
                400, f"Maximum number of guests is {listing.max_guests}"
            )
        return StayQuote(
            nights=nights,
            nightly_rate_cents=listing.price_cents,
            total_cents=nights * listing.price_cents,
            currency=listing.currency,
            timezone=listing.timezone,
            check_in_time=listing.check_in_time,
            check_out_time=listing.check_out_time,
        )

    async def assert_available(self, listing, data):
        if await self.repository.occupied(
            listing.venue_id, data.check_in, data.check_out
        ):
            raise HTTPException(409, "These dates are no longer available")

    async def quote(self, property_id, data):
        listing = await self.bookable_listing(property_id)
        quote = self.validate_dates(listing, data)
        await self.assert_available(listing, data)
        return quote

    async def create(self, property_id, data, user):
        # Serialize retries by account, then all aliases of the same apartment by venue.
        # The venue lock remains held until the reservation commit.
        await self.repository.lock_user(user.id)
        previous = await self.repository.previous_request(user.id, data.request_id)
        if previous:
            self.validate_expected_times(previous, data)
            if (
                previous.property_id,
                previous.check_in,
                previous.check_out,
                previous.guests,
                previous.total_cents,
                previous.currency,
            ) != (
                property_id,
                data.check_in,
                data.check_out,
                data.guests,
                data.expected_total_cents,
                data.expected_currency,
            ):
                raise HTTPException(409, "This request identifier was already used")
            return previous
        listing = await self.bookable_listing(property_id, lock=True)
        venue = await self.repository.lock_venue(listing.venue_id)
        if venue.owner_id == user.id:
            raise HTTPException(400, "You cannot reserve your own property")
        quote = self.validate_dates(listing, data)
        self.validate_expected_times(quote, data)
        if (data.expected_total_cents, data.expected_currency) != (
            quote.total_cents,
            quote.currency,
        ):
            raise HTTPException(409, "The price changed. Request a new quote")
        await self.assert_available(listing, data)
        stay = Stay(
            property_id=listing.id,
            venue_id=listing.venue_id,
            user_id=user.id,
            request_id=str(data.request_id),
            check_in=data.check_in,
            check_out=data.check_out,
            guests=data.guests,
            title=listing.title,
            city=listing.city,
            timezone=listing.timezone,
            check_in_time=listing.check_in_time,
            check_out_time=listing.check_out_time,
            contact_email=listing.contact_email,
            nightly_rate_cents=quote.nightly_rate_cents,
            total_cents=quote.total_cents,
            currency=quote.currency,
            status="confirmed",
        )
        return await self.repository.save(stay)

    @staticmethod
    def validate_expected_times(terms, data):
        for field in ("check_in_time", "check_out_time", "timezone"):
            expected = f"expected_{field}"
            if expected in data.model_fields_set and getattr(data, expected) != getattr(
                terms, field
            ):
                raise HTTPException(409, "Stay rules changed. Request a new quote")

    async def calendar(self, property_id, start, end):
        if not 1 <= (end - start).days <= 93:
            raise HTTPException(400, "Calendar range must be between 1 and 93 days")
        listing = await self.bookable_listing(property_id)
        return StayCalendar(
            start=start,
            end=end,
            occupied=await self.repository.occupied(listing.venue_id, start, end),
        )

    async def list(self, user, owner=False, offset=0, limit=20):
        items, total = await self.repository.list_for_user(
            user.id, owner, offset, limit
        )
        if owner and items:
            emails = await self.repository.guest_emails(
                {item.user_id for item in items}
            )
            items = [
                StayRead.model_validate(item).model_copy(
                    update={"guest_email": emails[item.user_id]}
                )
                for item in items
            ]
        return StayPage(items=items, total=total, has_next=offset + limit < total)

    async def cancel(self, stay_id, user):
        stay = await self.repository.get(stay_id, lock=True)
        if stay is None:
            raise HTTPException(404, "Reservation not found")
        # Owners can view stays; only the guest can cancel online.
        if stay.user_id != user.id:
            raise HTTPException(403, "This reservation belongs to another guest")
        if stay.status == "cancelled":
            return stay
        if stay.check_in <= self.today(stay.timezone):
            raise HTTPException(
                400, "Online cancellation is only available before arrival day"
            )
        stay.status = "cancelled"
        return await self.repository.save(stay)
