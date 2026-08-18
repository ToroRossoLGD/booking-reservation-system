from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.resource_review import ResourceReviewCreate
from app.services.favorite_resource_service import FavoriteResourceService
from app.services.notification_service import NotificationService
from app.services.resource_review_service import ResourceReviewService


@pytest.mark.asyncio
async def test_favorite_rejects_missing_resource_before_duplicate_lookup():
    service = FavoriteResourceService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=None)
    service.favorite_repository.get_by_user_and_resource = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.add_favorite(20, MagicMock(id=10))

    assert error.value.status_code == 404
    service.favorite_repository.get_by_user_and_resource.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_favorite_is_rejected():
    service = FavoriteResourceService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=MagicMock())
    service.favorite_repository.get_by_user_and_resource = AsyncMock(
        return_value=MagicMock()
    )

    with pytest.raises(HTTPException) as error:
        await service.add_favorite(20, MagicMock(id=10))

    assert error.value.status_code == 409
    assert error.value.detail == "Resource is already in favorites"


@pytest.mark.asyncio
async def test_add_favorite_uses_authenticated_user_identity():
    service = FavoriteResourceService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=MagicMock())
    service.favorite_repository.get_by_user_and_resource = AsyncMock(return_value=None)
    service.favorite_repository.create = AsyncMock(
        side_effect=lambda favorite: favorite
    )

    result = await service.add_favorite(20, MagicMock(id=42))

    assert result.user_id == 42
    assert result.resource_id == 20


@pytest.mark.asyncio
async def test_remove_missing_favorite_returns_not_found():
    service = FavoriteResourceService(AsyncMock())
    service.favorite_repository.get_by_user_and_resource = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.remove_favorite(20, MagicMock(id=10))

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_favorite_details_are_flattened_for_api_response():
    service = FavoriteResourceService(AsyncMock())
    created_at = datetime.now(UTC)
    favorite = SimpleNamespace(id=1, created_at=created_at)
    resource = SimpleNamespace(id=20, name="Court", resource_type="sports", capacity=8)
    venue = SimpleNamespace(id=5, name="Arena", address="Center 1")
    service.favorite_repository.get_user_favorites = AsyncMock(
        return_value=[(favorite, resource, venue)]
    )

    result = await service.get_my_favorites(MagicMock(id=10))

    assert result[0].favorite_id == 1
    assert result[0].resource_name == "Court"
    assert result[0].venue_name == "Arena"


@pytest.mark.asyncio
async def test_review_rejects_missing_resource():
    service = ResourceReviewService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.create_review(
            20, ResourceReviewCreate(rating=5), MagicMock(id=10)
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_customer_cannot_review_same_resource_twice():
    service = ResourceReviewService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=MagicMock())
    service.review_repository.get_by_user_and_resource = AsyncMock(
        return_value=MagicMock()
    )

    with pytest.raises(HTTPException) as error:
        await service.create_review(
            20, ResourceReviewCreate(rating=4), MagicMock(id=10)
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_review_copies_rating_comment_and_authenticated_user():
    service = ResourceReviewService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=MagicMock())
    service.review_repository.get_by_user_and_resource = AsyncMock(return_value=None)
    service.review_repository.create = AsyncMock(side_effect=lambda review: review)

    result = await service.create_review(
        20,
        ResourceReviewCreate(rating=4, comment="Great court"),
        MagicMock(id=10),
    )

    assert result.user_id == 10
    assert result.rating == 4
    assert result.comment == "Great court"


@pytest.mark.asyncio
async def test_rating_summary_is_rounded_to_two_decimals():
    service = ResourceReviewService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=MagicMock())
    service.review_repository.get_rating_summary = AsyncMock(return_value=(4.6666, 3))

    result = await service.get_rating_summary(20)

    assert result.average_rating == 4.67
    assert result.review_count == 3


@pytest.mark.asyncio
async def test_delete_review_is_scoped_to_authenticated_user():
    service = ResourceReviewService(AsyncMock())
    review = MagicMock()
    service.review_repository.get_by_user_and_resource = AsyncMock(return_value=review)
    service.review_repository.delete = AsyncMock()

    await service.delete_my_review(20, MagicMock(id=42))

    service.review_repository.get_by_user_and_resource.assert_awaited_once_with(
        user_id=42, resource_id=20
    )
    service.review_repository.delete.assert_awaited_once_with(review)


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 101])
async def test_notification_pagination_rejects_invalid_limit(limit):
    service = NotificationService(AsyncMock())

    with pytest.raises(HTTPException) as error:
        await service.get_my_notifications(10, limit, 0)

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_notification_pagination_rejects_negative_offset():
    service = NotificationService(AsyncMock())

    with pytest.raises(HTTPException) as error:
        await service.get_my_notifications(10, 20, -1)

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_notification_pagination_propagates_filter_and_metadata():
    service = NotificationService(AsyncMock())
    service.notification_repository.get_by_user_id = AsyncMock(return_value=["item"])
    service.notification_repository.count_by_user_id = AsyncMock(return_value=21)

    result = await service.get_my_notifications(10, 20, 0, is_read=False)

    assert result == {
        "items": ["item"],
        "total": 21,
        "limit": 20,
        "offset": 0,
        "has_next": True,
    }
    service.notification_repository.get_by_user_id.assert_awaited_once_with(
        user_id=10, limit=20, offset=0, is_read=False
    )


@pytest.mark.asyncio
async def test_marking_already_read_notification_is_idempotent():
    service = NotificationService(AsyncMock())
    notification = MagicMock(is_read=True)
    service.notification_repository.get_by_id_for_user = AsyncMock(
        return_value=notification
    )
    service.notification_repository.mark_as_read = AsyncMock()

    result = await service.mark_notification_as_read(1, 10)

    assert result is notification
    service.notification_repository.mark_as_read.assert_not_awaited()
