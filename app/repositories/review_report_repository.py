from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_report import ReviewReport


class ReviewReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, report_id: int) -> ReviewReport | None:
        result = await self.db.execute(
            select(ReviewReport).where(ReviewReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def get_by_review_and_reporter(
        self, review_id: int, reporter_id: int
    ) -> ReviewReport | None:
        result = await self.db.execute(
            select(ReviewReport).where(
                ReviewReport.review_id == review_id,
                ReviewReport.reporter_id == reporter_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, report: ReviewReport) -> ReviewReport:
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def update(self, report: ReviewReport) -> ReviewReport:
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def list_reports(
        self, status: str | None, limit: int, offset: int
    ) -> list[ReviewReport]:
        query = select(ReviewReport)
        if status is not None:
            query = query.where(ReviewReport.status == status)
        result = await self.db.execute(
            query.order_by(ReviewReport.created_at).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def count_reports(self, status: str | None) -> int:
        query = select(func.count(ReviewReport.id))
        if status is not None:
            query = query.where(ReviewReport.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()
