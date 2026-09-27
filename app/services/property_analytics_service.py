import hashlib
import hmac
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import extract, func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.models.property_listing import PropertyListing
from app.models.property_view import PropertyView
from app.models.stay import Stay
from app.models.venue import Venue
from app.schemas.property_analytics import PropertyAnalyticsMonth


class PropertyAnalyticsService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def today():
        return datetime.now(UTC).date()

    async def record_view(self, property_id, visitor_id, user=None):
        row = (
            await self.db.execute(
                select(PropertyListing.is_published, Venue.owner_id)
                .join(Venue)
                .where(PropertyListing.id == property_id)
            )
        ).one_or_none()
        if row is None or not row.is_published:
            raise HTTPException(404, "Listing not found")
        if user is not None and user.id == row.owner_id:
            return
        day = self.today()
        digest = hmac.new(
            settings.JWT_SECRET.encode(),
            f"property-view|{property_id}|{day}|{visitor_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        await self.db.execute(
            insert(PropertyView)
            .values(property_id=property_id, viewed_on=day, visitor_hash=digest)
            .on_conflict_do_nothing(
                index_elements=["property_id", "viewed_on", "visitor_hash"]
            )
        )
        await self.db.commit()

    async def overview(self, user, year, property_id=None):
        properties = (
            await self.db.execute(
                select(
                    PropertyListing.id,
                    PropertyListing.title,
                    PropertyListing.offer_type,
                )
                .join(Venue)
                .where(Venue.owner_id == user.id)
                .order_by(PropertyListing.title, PropertyListing.id)
            )
        ).all()
        ids = [p.id for p in properties]
        if property_id is not None:
            if property_id not in ids:
                raise HTTPException(404, "Listing not found")
            ids = [property_id]
        months = [PropertyAnalyticsMonth(month=month) for month in range(1, 13)]
        start, end = date(year, 1, 1), date(year + 1, 1, 1)
        if ids:
            month = extract("month", PropertyView.viewed_on)
            views = await self.db.execute(
                select(month, func.count())
                .where(
                    PropertyView.property_id.in_(ids),
                    PropertyView.viewed_on >= start,
                    PropertyView.viewed_on < end,
                )
                .group_by(month)
            )
            for month_number, count in views.all():
                months[int(month_number) - 1].views = count
            stays = await self.db.execute(
                select(
                    Stay.check_in,
                    Stay.check_out,
                    Stay.status,
                    Stay.total_cents,
                    Stay.currency,
                )
                .join(Venue)
                .where(
                    Venue.owner_id == user.id,
                    Stay.property_id.in_(ids),
                    Stay.check_in < end,
                    Stay.check_out > start,
                )
            )
            for stay in stays.all():
                if start <= stay.check_in < end:
                    bucket = months[stay.check_in.month - 1]
                    if stay.status == "confirmed":
                        bucket.reservations += 1
                    elif stay.status == "cancelled":
                        bucket.cancelled += 1
                if stay.status != "confirmed":
                    continue
                duration = (stay.check_out - stay.check_in).days
                for bucket in months:
                    left = max(stay.check_in, date(year, bucket.month, 1))
                    right = min(
                        stay.check_out,
                        date(year + 1, 1, 1)
                        if bucket.month == 12
                        else date(year, bucket.month + 1, 1),
                    )
                    if right <= left:
                        continue
                    bucket.nights += (right - left).days
                    # Cumulative rounding keeps the split equal to the agreed total.
                    value = (
                        stay.total_cents * (right - stay.check_in).days // duration
                        - stay.total_cents * (left - stay.check_in).days // duration
                    )
                    bucket.booked_value_cents[stay.currency] = (
                        bucket.booked_value_cents.get(stay.currency, 0) + value
                    )
        return dict(
            year=year,
            properties=[
                dict(id=p.id, title=p.title, offer_type=p.offer_type)
                for p in properties
            ],
            months=months,
        )
