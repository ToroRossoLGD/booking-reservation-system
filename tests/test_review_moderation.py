from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.resource_review import ReviewStatus
from app.models.review_report import ReviewReportStatus
from app.repositories.resource_review_repository import ResourceReviewRepository
from app.schemas.resource_review import (
    OwnerResponseUpdate,
    ReviewModerationUpdate,
    ReviewReportCreate,
    ReviewReportDecision,
)
from app.services.resource_review_service import ResourceReviewService
from app.services.review_moderation_service import ReviewModerationService


@pytest.mark.asyncio
async def test_public_review_query_filters_hidden_reviews():
    db = MagicMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=query_result)
    repository = ResourceReviewRepository(db)

    await repository.get_by_resource_id(20)

    statement = db.execute.await_args.args[0]
    assert "resource_reviews.status" in str(statement)
    assert ReviewStatus.VISIBLE.value in statement.compile().params.values()


@pytest.mark.asyncio
async def test_rating_summary_filters_hidden_reviews():
    db = MagicMock()
    query_result = MagicMock()
    query_result.one.return_value = (4.5, 2)
    db.execute = AsyncMock(return_value=query_result)
    repository = ResourceReviewRepository(db)

    result = await repository.get_rating_summary(20)

    statement = db.execute.await_args.args[0]
    assert result == (4.5, 2)
    assert "resource_reviews.status" in str(statement)
    assert ReviewStatus.VISIBLE.value in statement.compile().params.values()


@pytest.mark.asyncio
async def test_venue_owner_can_respond_to_review():
    service = ResourceReviewService(AsyncMock())
    review = MagicMock(id=7, resource_id=20, owner_response=None)
    service.review_repository.get_by_id = AsyncMock(return_value=review)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=20, venue_id=5)
    )
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=5, owner_id=30)
    )
    service.review_repository.update = AsyncMock(side_effect=lambda item: item)

    result = await service.set_owner_response(
        review_id=7,
        data=OwnerResponseUpdate(response="Thank you for visiting."),
        current_user=MagicMock(id=30, role="owner"),
    )

    assert result.owner_response == "Thank you for visiting."
    assert result.owner_responded_at is not None
    service.review_repository.update.assert_awaited_once_with(review)


@pytest.mark.asyncio
async def test_owner_cannot_respond_for_another_venue():
    service = ResourceReviewService(AsyncMock())
    service.review_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=7, resource_id=20)
    )
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=20, venue_id=5)
    )
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=5, owner_id=99)
    )

    with pytest.raises(HTTPException) as error:
        await service.set_owner_response(
            review_id=7,
            data=OwnerResponseUpdate(response="Not my venue"),
            current_user=MagicMock(id=30, role="owner"),
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_customer_can_report_visible_review():
    service = ResourceReviewService(AsyncMock())
    review = MagicMock(id=7, user_id=11, status=ReviewStatus.VISIBLE.value)
    service.review_repository.get_by_id = AsyncMock(return_value=review)
    service.report_repository.get_by_review_and_reporter = AsyncMock(return_value=None)
    service.report_repository.create = AsyncMock(side_effect=lambda report: report)

    report = await service.report_review(
        review_id=7,
        data=ReviewReportCreate(reason="spam", details="Repeated advertising"),
        current_user=MagicMock(id=10),
    )

    assert report.review_id == 7
    assert report.reporter_id == 10
    assert report.reason == "spam"
    assert report.details == "Repeated advertising"


@pytest.mark.asyncio
async def test_customer_cannot_report_own_review():
    service = ResourceReviewService(AsyncMock())
    service.review_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=7, user_id=10, status=ReviewStatus.VISIBLE.value)
    )
    service.report_repository.get_by_review_and_reporter = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.report_review(
            7,
            ReviewReportCreate(reason="other"),
            MagicMock(id=10),
        )

    assert error.value.status_code == 400
    service.report_repository.get_by_review_and_reporter.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_report_is_rejected():
    service = ResourceReviewService(AsyncMock())
    service.review_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=7, user_id=11, status=ReviewStatus.VISIBLE.value)
    )
    service.report_repository.get_by_review_and_reporter = AsyncMock(
        return_value=MagicMock()
    )

    with pytest.raises(HTTPException) as error:
        await service.report_review(
            7,
            ReviewReportCreate(reason="harassment"),
            MagicMock(id=10),
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_hiding_reported_review_resolves_report_with_audit_metadata():
    service = ReviewModerationService(AsyncMock())
    report = MagicMock(
        id=3,
        review_id=7,
        status=ReviewReportStatus.PENDING.value,
        reviewed_by=None,
        reviewed_at=None,
    )
    review = MagicMock(id=7, status=ReviewStatus.VISIBLE.value)
    service.report_repository.get_by_id = AsyncMock(return_value=report)
    service.review_repository.get_by_id = AsyncMock(return_value=review)
    service.review_repository.update = AsyncMock(side_effect=lambda item: item)
    service.report_repository.update = AsyncMock(side_effect=lambda item: item)

    result = await service.decide_report(
        report_id=3,
        data=ReviewReportDecision(
            decision="hide_review", resolution_note="Confirmed harassment"
        ),
        current_user=MagicMock(id=100, role="admin"),
    )

    assert review.status == ReviewStatus.HIDDEN.value
    assert review.moderated_by == 100
    assert review.moderation_reason == "Confirmed harassment"
    assert result.status == ReviewReportStatus.RESOLVED.value
    assert result.reviewed_by == 100


@pytest.mark.asyncio
async def test_dismissing_report_does_not_change_review():
    service = ReviewModerationService(AsyncMock())
    report = MagicMock(
        id=3,
        review_id=7,
        status=ReviewReportStatus.PENDING.value,
    )
    service.report_repository.get_by_id = AsyncMock(return_value=report)
    service.report_repository.update = AsyncMock(side_effect=lambda item: item)
    service.review_repository.get_by_id = AsyncMock()

    result = await service.decide_report(
        report_id=3,
        data=ReviewReportDecision(
            decision="dismiss", resolution_note="No policy violation"
        ),
        current_user=MagicMock(id=100),
    )

    assert result.status == ReviewReportStatus.DISMISSED.value
    service.review_repository.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_can_restore_hidden_review():
    service = ReviewModerationService(AsyncMock())
    review = MagicMock(id=7, status=ReviewStatus.HIDDEN.value)
    service.review_repository.get_by_id = AsyncMock(return_value=review)
    service.review_repository.update = AsyncMock(side_effect=lambda item: item)

    result = await service.moderate_review(
        review_id=7,
        data=ReviewModerationUpdate(
            status="visible", reason="Moderation decision overturned"
        ),
        current_user=MagicMock(id=100),
    )

    assert result.status == ReviewStatus.VISIBLE.value
    assert result.moderated_by == 100
    assert result.moderated_at is not None


@pytest.mark.asyncio
async def test_report_queue_returns_pagination_metadata():
    service = ReviewModerationService(AsyncMock())
    service.report_repository.list_reports = AsyncMock(return_value=[MagicMock()])
    service.report_repository.count_reports = AsyncMock(return_value=21)

    result = await service.list_reports("pending", limit=20, offset=0)

    assert result["total"] == 21
    assert result["has_next"] is True
    service.report_repository.list_reports.assert_awaited_once_with(
        status="pending", limit=20, offset=0
    )


@pytest.mark.asyncio
async def test_already_decided_report_cannot_be_changed():
    service = ReviewModerationService(AsyncMock())
    service.report_repository.get_by_id = AsyncMock(
        return_value=MagicMock(status=ReviewReportStatus.RESOLVED.value)
    )

    with pytest.raises(HTTPException) as error:
        await service.decide_report(
            3,
            ReviewReportDecision(decision="dismiss", resolution_note="Changed mind"),
            MagicMock(id=100),
        )

    assert error.value.status_code == 409
