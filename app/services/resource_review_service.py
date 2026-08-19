from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_review import ResourceReview, ReviewStatus
from app.models.review_report import ReviewReport
from app.models.user import User
from app.repositories.resource_repository import ResourceRepository
from app.repositories.resource_review_repository import ResourceReviewRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.resource_review import (
    OwnerResponseUpdate,
    ResourceRatingSummaryRead,
    ResourceReviewCreate,
    ReviewReportCreate,
)


class ResourceReviewService:
    def __init__(self, db: AsyncSession):
        self.review_repository = ResourceReviewRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.venue_repository = VenueRepository(db)
        self.report_repository = ReviewReportRepository(db)

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

    async def set_owner_response(
        self,
        review_id: int,
        data: OwnerResponseUpdate,
        current_user: User,
    ) -> ResourceReview:
        review = await self.review_repository.get_by_id(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found")

        resource = await self.resource_repository.get_by_id(review.resource_id)
        venue = (
            await self.venue_repository.get_by_id(resource.venue_id)
            if resource is not None
            else None
        )
        if current_user.role != "admin" and (
            venue is None or venue.owner_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can respond only to reviews for your own venues",
            )

        review.owner_response = data.response
        review.owner_responded_at = datetime.now(UTC)
        return await self.review_repository.update(review)

    async def report_review(
        self,
        review_id: int,
        data: ReviewReportCreate,
        current_user: User,
    ) -> ReviewReport:
        review = await self.review_repository.get_by_id(review_id)
        if review is None or review.status != ReviewStatus.VISIBLE.value:
            raise HTTPException(status_code=404, detail="Review not found")
        if review.user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot report your own review",
            )
        existing = await self.report_repository.get_by_review_and_reporter(
            review_id=review_id, reporter_id=current_user.id
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already reported this review",
            )

        return await self.report_repository.create(
            ReviewReport(
                review_id=review_id,
                reporter_id=current_user.id,
                reason=data.reason,
                details=data.details,
            )
        )
