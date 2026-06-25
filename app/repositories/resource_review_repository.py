from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_review import ResourceReview


class ResourceReviewRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_and_resource(
        self,
        user_id: int,
        resource_id: int,
    ) -> ResourceReview | None:
        result = await self.db.execute(
            select(ResourceReview).where(
                ResourceReview.user_id == user_id,
                ResourceReview.resource_id == resource_id,
            )
        )

        return result.scalar_one_or_none()

    async def create(
        self,
        review: ResourceReview,
    ) -> ResourceReview:
        self.db.add(review)
        await self.db.commit()
        await self.db.refresh(review)
        return review

    async def get_by_resource_id(
        self,
        resource_id: int,
    ) -> list[ResourceReview]:
        result = await self.db.execute(
            select(ResourceReview)
            .where(ResourceReview.resource_id == resource_id)
            .order_by(ResourceReview.created_at.desc())
        )

        return list(result.scalars().all())

    async def delete(
        self,
        review: ResourceReview,
    ) -> None:
        await self.db.delete(review)
        await self.db.commit()

    async def get_rating_summary(
        self,
        resource_id: int,
    ) -> tuple[float, int]:
        result = await self.db.execute(
            select(
                func.coalesce(func.avg(ResourceReview.rating), 0),
                func.count(ResourceReview.id),
            ).where(ResourceReview.resource_id == resource_id)
        )

        average_rating, review_count = result.one()

        return float(average_rating), int(review_count)
