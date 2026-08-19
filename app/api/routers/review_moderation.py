from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.resource_review import (
    ResourceReviewRead,
    ReviewModerationUpdate,
    ReviewReportDecision,
    ReviewReportListRead,
    ReviewReportRead,
)
from app.services.review_moderation_service import ReviewModerationService

router = APIRouter(
    prefix="/review-moderation",
    tags=["Review Moderation"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("/reports", response_model=ReviewReportListRead)
async def list_review_reports(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await ReviewModerationService(db).list_reports(status, limit, offset)


@router.patch("/reports/{report_id}", response_model=ReviewReportRead)
async def decide_review_report(
    report_id: int,
    data: ReviewReportDecision,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    return await ReviewModerationService(db).decide_report(
        report_id=report_id, data=data, current_user=current_user
    )


@router.patch("/reviews/{review_id}", response_model=ResourceReviewRead)
async def moderate_review(
    review_id: int,
    data: ReviewModerationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    return await ReviewModerationService(db).moderate_review(
        review_id=review_id, data=data, current_user=current_user
    )
