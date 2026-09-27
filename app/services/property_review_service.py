from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.property_listing import PropertyListing
from app.models.property_review import PropertyReview
from app.models.venue import Venue
from app.repositories.stay_repository import StayRepository
from app.services.stay_service import StayService


class PropertyReviewService:
    def __init__(self, db):
        self.db = db

    async def owned_stay(self, stay_id, user, lock=False):
        stay = await StayRepository(self.db).get(stay_id, lock=lock)
        if stay is None or stay.user_id != user.id:
            raise HTTPException(404, "Stay not found")
        return stay

    async def mine(self, stay_id, user):
        await self.owned_stay(stay_id, user)
        return await self.db.scalar(
            select(PropertyReview).where(PropertyReview.stay_id == stay_id)
        )

    async def create(self, stay_id, data, user):
        # Same stay lock as cancellation; concurrent retries serialize here.
        stay = await self.owned_stay(stay_id, user, lock=True)
        previous = await self.db.scalar(
            select(PropertyReview).where(PropertyReview.stay_id == stay_id)
        )
        if previous:
            if (previous.rating, previous.comment) != (data.rating, data.comment):
                raise HTTPException(409, "This stay already has a review")
            return previous
        if stay.status != "confirmed" or stay.check_out >= StayService.today(
            stay.timezone
        ):
            raise HTTPException(400, "Reviews open the day after checkout")
        owner_id = await self.db.scalar(
            select(Venue.owner_id).where(Venue.id == stay.venue_id)
        )
        if owner_id == user.id:
            raise HTTPException(400, "You cannot review your own property")
        review = PropertyReview(
            stay_id=stay.id, property_id=stay.property_id, **data.model_dump()
        )
        self.db.add(review)
        await self.db.commit()
        await self.db.refresh(review)
        return review

    async def public(self, property_id, offset=0, limit=10):
        listing = await self.db.get(PropertyListing, property_id)
        if (
            listing is None
            or not listing.is_published
            or listing.offer_type != "short_stay"
        ):
            raise HTTPException(404, "Nightly listing not found")
        query = select(PropertyReview).where(PropertyReview.property_id == property_id)
        aggregate = (
            await self.db.execute(
                select(
                    func.count(PropertyReview.id), func.avg(PropertyReview.rating)
                ).where(PropertyReview.property_id == property_id)
            )
        ).one()
        items = await self.db.scalars(
            query.order_by(PropertyReview.created_at.desc(), PropertyReview.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return dict(
            items=list(items.all()),
            total=aggregate[0],
            average_rating=round(aggregate[1], 2) if aggregate[1] is not None else None,
            has_next=offset + limit < aggregate[0],
        )
