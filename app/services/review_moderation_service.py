from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_review import ReviewStatus
from app.models.review_report import ReviewReportStatus
from app.models.user import User
from app.repositories.resource_review_repository import ResourceReviewRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.schemas.resource_review import ReviewModerationUpdate, ReviewReportDecision


class ReviewModerationService:
    def __init__(self, db: AsyncSession):
        self.review_repository = ResourceReviewRepository(db)
        self.report_repository = ReviewReportRepository(db)

    async def list_reports(
        self, status_filter: str | None, limit: int, offset: int
    ) -> dict:
        valid_statuses = {item.value for item in ReviewReportStatus}
        if status_filter is not None and status_filter not in valid_statuses:
            raise HTTPException(status_code=400, detail="Invalid report status")
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=400, detail="limit must be between 1 and 100"
            )
        if offset < 0:
            raise HTTPException(status_code=400, detail="offset must be non-negative")

        items = await self.report_repository.list_reports(
            status=status_filter, limit=limit, offset=offset
        )
        total = await self.report_repository.count_reports(status_filter)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
        }

    async def decide_report(
        self,
        report_id: int,
        data: ReviewReportDecision,
        current_user: User,
    ):
        report = await self.report_repository.get_by_id(report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Review report not found")
        if report.status != ReviewReportStatus.PENDING.value:
            raise HTTPException(
                status_code=409, detail="Review report is already decided"
            )

        if data.decision == "hide_review":
            review = await self.review_repository.get_by_id(report.review_id)
            if review is None:
                raise HTTPException(status_code=404, detail="Reported review not found")
            review.status = ReviewStatus.HIDDEN.value
            review.moderation_reason = data.resolution_note
            review.moderated_by = current_user.id
            review.moderated_at = datetime.now(UTC)
            await self.review_repository.update(review)
            report.status = ReviewReportStatus.RESOLVED.value
        else:
            report.status = ReviewReportStatus.DISMISSED.value

        report.reviewed_by = current_user.id
        report.reviewed_at = datetime.now(UTC)
        report.resolution_note = data.resolution_note
        return await self.report_repository.update(report)

    async def moderate_review(
        self,
        review_id: int,
        data: ReviewModerationUpdate,
        current_user: User,
    ):
        review = await self.review_repository.get_by_id(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found")
        review.status = data.status
        review.moderation_reason = data.reason
        review.moderated_by = current_user.id
        review.moderated_at = datetime.now(UTC)
        return await self.review_repository.update(review)
