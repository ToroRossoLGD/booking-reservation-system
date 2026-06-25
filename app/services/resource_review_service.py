from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_review import ResourceReview
from app.models.user import User
from app.repositories.resource_repository import ResourceRepository
from app.repositories.resource_review_repository import ResourceReviewRepository
from app.schemas.resource_review import (
    ResourceRatingSummaryRead,
    ResourceReviewCreate,
)


class ResourceReviewService:
    def __init__(self, db: AsyncSession):
        self.review_repository = ResourceReviewRepository(db)
        self.resource_repository = ResourceRepository(db)

    async def create_review(
        self,
        resource_id: int,
        data: ResourceReviewCreate,
        current_user: User,
    ) -> ResourceReview:
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        existing_review = await self.review_repository.get_by_user_and_resource(
            user_id=current_user.id,
            resource_id=resource_id,
        )

        if existing_review is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already reviewed this resource",
            )

        review = ResourceReview(
            user_id=current_user.id,
            resource_id=resource_id,
            rating=data.rating,
            comment=data.comment,
        )

        return await self.review_repository.create(review)

    async def get_resource_reviews(
        self,
        resource_id: int,
    ):
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        return await self.review_repository.get_by_resource_id(resource_id)

    async def get_rating_summary(
        self,
        resource_id: int,
    ) -> ResourceRatingSummaryRead:
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        average_rating, review_count = await self.review_repository.get_rating_summary(
            resource_id
        )

        return ResourceRatingSummaryRead(
            resource_id=resource_id,
            average_rating=round(average_rating, 2),
            review_count=review_count,
        )

    async def delete_my_review(
        self,
        resource_id: int,
        current_user: User,
    ) -> None:
        review = await self.review_repository.get_by_user_and_resource(
            user_id=current_user.id,
            resource_id=resource_id,
        )

        if review is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found",
            )

        await self.review_repository.delete(review)
