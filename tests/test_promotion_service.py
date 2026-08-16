from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.promotion import PromotionCreate
from app.services.promotion_service import PromotionService


def promotion_data() -> PromotionCreate:
    now = datetime.now(UTC)
    return PromotionCreate(
        code="summer_25",
        discount_percent=25,
        valid_from=now,
        valid_until=now + timedelta(days=30),
        max_redemptions=100,
    )


@pytest.mark.asyncio
async def test_owner_can_create_normalized_promotion_for_own_venue():
    service = PromotionService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=5, owner_id=10)
    )
    service.promotion_repository.create = AsyncMock(
        side_effect=lambda promotion: promotion
    )

    promotion = await service.create_promotion(
        venue_id=5,
        data=promotion_data(),
        current_user=MagicMock(id=10, role="owner"),
    )

    assert promotion.code == "SUMMER_25"
    assert promotion.discount_percent == 25
    assert promotion.max_redemptions == 100


@pytest.mark.asyncio
async def test_owner_cannot_manage_another_owners_promotions():
    service = PromotionService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=5, owner_id=99)
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.list_promotions(
            venue_id=5,
            current_user=MagicMock(id=10, role="owner"),
        )

    assert exception_info.value.status_code == 403


@pytest.mark.asyncio
async def test_promotion_rejects_invalid_validity_window():
    service = PromotionService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=5, owner_id=10)
    )
    data = promotion_data()
    data.valid_until = data.valid_from

    with pytest.raises(HTTPException) as exception_info:
        await service.create_promotion(
            venue_id=5,
            data=data,
            current_user=MagicMock(id=10, role="owner"),
        )

    assert exception_info.value.status_code == 400
