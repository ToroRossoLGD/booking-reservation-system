from datetime import UTC, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.availability_exception import AvailabilityExceptionCreate
from app.schemas.availability_rule import AvailabilityRuleCreate
from app.services.availability_exception_service import AvailabilityExceptionService
from app.services.availability_rule_service import AvailabilityRuleService


def user(user_id=10, role="owner"):
    return MagicMock(id=user_id, role=role)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_type", "method_name"),
    [
        (AvailabilityRuleService, "_validate_resource_management_permission"),
        (AvailabilityExceptionService, "_validate_resource_management_permission"),
    ],
)
async def test_management_rejects_missing_resource(service_type, method_name):
    service = service_type(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await getattr(service, method_name)(20, user())

    assert error.value.status_code == 404
    assert error.value.detail == "Resource not found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service_type",
    [AvailabilityRuleService, AvailabilityExceptionService],
)
async def test_management_rejects_missing_venue(service_type):
    service = service_type(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(venue_id=5)
    )
    service.venue_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service._validate_resource_management_permission(20, user())

    assert error.value.status_code == 404
    assert error.value.detail == "Venue not found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service_type",
    [AvailabilityRuleService, AvailabilityExceptionService],
)
async def test_non_owner_cannot_manage_another_venue(service_type):
    service = service_type(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(venue_id=5)
    )
    service.venue_repository.get_by_id = AsyncMock(return_value=MagicMock(owner_id=99))

    with pytest.raises(HTTPException) as error:
        await service._validate_resource_management_permission(20, user())

    assert error.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "admin"])
async def test_owner_and_admin_can_manage_rules(role):
    service = AvailabilityRuleService(AsyncMock())
    resource = MagicMock(venue_id=5)
    service.resource_repository.get_by_id = AsyncMock(return_value=resource)
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(owner_id=10 if role == "owner" else 99)
    )

    result = await service._validate_resource_management_permission(20, user(role=role))

    assert result is resource


@pytest.mark.asyncio
async def test_overlapping_rule_is_rejected_without_creation():
    service = AvailabilityRuleService(AsyncMock())
    service._validate_resource_management_permission = AsyncMock()
    service.rule_repository.has_overlapping_rule = AsyncMock(return_value=True)
    service.rule_repository.create = AsyncMock()
    data = AvailabilityRuleCreate(weekday=0, start_time=time(9), end_time=time(17))

    with pytest.raises(HTTPException) as error:
        await service.create_rule(20, data, user())

    assert error.value.status_code == 409
    service.rule_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_rule_creation_invalidates_slot_cache():
    service = AvailabilityRuleService(AsyncMock())
    service._validate_resource_management_permission = AsyncMock()
    service.rule_repository.has_overlapping_rule = AsyncMock(return_value=False)
    service.rule_repository.create = AsyncMock(side_effect=lambda rule: rule)
    data = AvailabilityRuleCreate(weekday=2, start_time=time(8), end_time=time(12))

    with patch(
        "app.services.availability_rule_service."
        "delete_available_slots_cache_for_resource",
        new_callable=AsyncMock,
    ) as invalidate:
        result = await service.create_rule(20, data, user())

    assert result.weekday == 2
    assert result.resource_id == 20
    invalidate.assert_awaited_once_with(20)


@pytest.mark.asyncio
async def test_overlapping_exception_is_rejected_without_creation():
    service = AvailabilityExceptionService(AsyncMock())
    service._validate_resource_management_permission = AsyncMock()
    service.exception_repository.has_overlapping_exception = AsyncMock(
        return_value=True
    )
    service.exception_repository.create = AsyncMock()
    start = datetime.now(UTC) + timedelta(days=1)
    data = AvailabilityExceptionCreate(
        start_time=start,
        end_time=start + timedelta(hours=2),
        reason="Maintenance",
    )

    with pytest.raises(HTTPException) as error:
        await service.create_exception(20, data, user())

    assert error.value.status_code == 409
    service.exception_repository.create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["rule", "exception"])
async def test_delete_rejects_record_from_different_resource(kind):
    if kind == "rule":
        service = AvailabilityRuleService(AsyncMock())
        service._validate_resource_management_permission = AsyncMock()
        service.rule_repository.get_by_id = AsyncMock(
            return_value=MagicMock(resource_id=99)
        )
        call = service.delete_rule(20, 1, user())
    else:
        service = AvailabilityExceptionService(AsyncMock())
        service._validate_resource_management_permission = AsyncMock()
        service.exception_repository.get_by_id = AsyncMock(
            return_value=MagicMock(resource_id=99)
        )
        call = service.delete_exception(20, 1, user())

    with pytest.raises(HTTPException) as error:
        await call

    assert error.value.status_code == 404


@pytest.mark.parametrize(
    "values",
    [
        {"weekday": -1, "start_time": time(9), "end_time": time(10)},
        {"weekday": 7, "start_time": time(9), "end_time": time(10)},
        {"weekday": 1, "start_time": time(10), "end_time": time(10)},
        {"weekday": 1, "start_time": time(11), "end_time": time(10)},
    ],
)
def test_rule_schema_rejects_invalid_weekday_or_interval(values):
    with pytest.raises(ValidationError):
        AvailabilityRuleCreate(**values)


@pytest.mark.parametrize("missing_timezone", ["start", "end"])
def test_exception_schema_requires_timezone_on_both_boundaries(missing_timezone):
    aware = datetime.now(UTC) + timedelta(days=1)
    start = aware.replace(tzinfo=None) if missing_timezone == "start" else aware
    end = (
        (aware + timedelta(hours=1)).replace(tzinfo=None)
        if missing_timezone == "end"
        else aware + timedelta(hours=1)
    )

    with pytest.raises(ValidationError):
        AvailabilityExceptionCreate(start_time=start, end_time=end)
