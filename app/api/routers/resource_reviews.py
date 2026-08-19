from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.resource_review import (
    OwnerResponseUpdate,
    ResourceRatingSummaryRead,
    ResourceReviewCreate,
    ResourceReviewRead,
    ReviewReportCreate,
    ReviewReportRead,
)
from app.services.resource_review_service import ResourceReviewService

router = APIRouter(
    prefix="/resources",
    tags=["Resource Reviews"],
)


@router.post(
    "/{resource_id}/reviews",
    response_model=ResourceReviewRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource_review(
    resource_id: int,
    data: ResourceReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ResourceReviewService(db)

    return await service.create_review(
        resource_id=resource_id,
        data=data,
        current_user=current_user,
    )


@router.get(
    "/{resource_id}/reviews",
    response_model=list[ResourceReviewRead],
)
async def get_resource_reviews(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = ResourceReviewService(db)

    return await service.get_resource_reviews(
        resource_id=resource_id,
    )


@router.get(
    "/{resource_id}/rating-summary",
    response_model=ResourceRatingSummaryRead,
)
async def get_resource_rating_summary(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = ResourceReviewService(db)

    return await service.get_rating_summary(
        resource_id=resource_id,
    )


@router.delete(
    "/{resource_id}/reviews/my",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_my_resource_review(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ResourceReviewService(db)

    await service.delete_my_review(
        resource_id=resource_id,
        current_user=current_user,
    )


@router.put(
    "/reviews/{review_id}/owner-response",
    response_model=ResourceReviewRead,
)
async def set_review_owner_response(
    review_id: int,
    data: OwnerResponseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await ResourceReviewService(db).set_owner_response(
        review_id=review_id, data=data, current_user=current_user
    )


@router.post(
    "/reviews/{review_id}/reports",
    response_model=ReviewReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def report_review(
    review_id: int,
    data: ReviewReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ResourceReviewService(db).report_review(
        review_id=review_id, data=data, current_user=current_user
    )
