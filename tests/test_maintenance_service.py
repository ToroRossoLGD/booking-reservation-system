from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.maintenance import MaintenanceWorkOrder, WorkOrderStatus
from app.schemas.maintenance import (
    WorkOrderAssignment,
    WorkOrderComment,
    WorkOrderCreate,
    WorkOrderTransition,
    WorkOrderUpdate,
)
from app.services.maintenance_service import MaintenanceService


def user(user_id=10, role="owner"):
    return MagicMock(id=user_id, role=role)


def venue(owner_id=10):
    return MagicMock(id=7, owner_id=owner_id)


def work_order(**changes):
    values = {
        "id": 4,
        "venue_id": 7,
        "resource_id": 3,
        "title": "Broken court light",
        "description": "North fixture is flickering",
        "priority": "high",
        "status": "open",
        "reported_by_id": 20,
        "assigned_to_id": None,
        "due_at": None,
        "resolved_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(changes)
    return MagicMock(**values)


def configure_owner(service):
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())


@pytest.mark.asyncio
async def test_owner_creates_resource_work_order_with_activity():
    service = MaintenanceService(AsyncMock())
    configure_owner(service)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=3, venue_id=7)
    )
    service.repository.create = AsyncMock(side_effect=lambda item, activity: item)
    data = WorkOrderCreate(
        resource_id=3,
        title="Broken court light",
        description="North fixture is flickering",
        priority="high",
    )

    result = await service.create(7, data, user())

    assert isinstance(result, MaintenanceWorkOrder)
    assert result.status == WorkOrderStatus.OPEN.value
    assert result.reported_by_id == 10
    activity = service.repository.create.await_args.args[1]
    assert activity.activity_type == "created"
    assert activity.details["resource_id"] == 3


@pytest.mark.asyncio
async def test_work_order_rejects_resource_from_another_venue():
    service = MaintenanceService(AsyncMock())
    configure_owner(service)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=3, venue_id=99)
    )

    with pytest.raises(HTTPException) as error:
        await service.create(
            7,
            WorkOrderCreate(
                resource_id=3,
                title="Problem",
                description="Detailed problem",
            ),
            user(),
        )

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_check_in_agent_can_report_and_view_maintenance():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.staff_repository.has_role = AsyncMock(return_value=True)
    service.repository.create = AsyncMock(side_effect=lambda item, activity: item)

    result = await service.create(
        7,
        WorkOrderCreate(title="Door issue", description="Door will not lock"),
        user(20, "customer"),
    )

    assert result.reported_by_id == 20
    service.staff_repository.has_role.assert_awaited_once_with(
        7, 20, {"manager", "check_in_agent"}
    )


@pytest.mark.asyncio
async def test_check_in_agent_cannot_manage_work_order():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.staff_repository.has_role = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as error:
        await service.update(
            7, 4, WorkOrderUpdate(priority="urgent"), user(20, "customer")
        )

    assert error.value.status_code == 403
    service.staff_repository.has_role.assert_awaited_once_with(7, 20, {"manager"})


@pytest.mark.asyncio
async def test_manager_updates_work_order_and_records_before_after_values():
    service = MaintenanceService(AsyncMock())
    item = work_order(priority="medium")
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.staff_repository.has_role = AsyncMock(return_value=True)
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.save = AsyncMock(side_effect=lambda value, activity: value)

    result = await service.update(
        7, 4, WorkOrderUpdate(priority="urgent"), user(20, "customer")
    )

    assert result.priority == "urgent"
    activity = service.repository.save.await_args.args[1]
    assert activity.details == {
        "before": {"priority": "medium"},
        "after": {"priority": "urgent"},
    }


def test_empty_work_order_update_is_rejected():
    with pytest.raises(ValidationError):
        WorkOrderUpdate()


@pytest.mark.asyncio
async def test_manager_assigns_active_venue_staff():
    service = MaintenanceService(AsyncMock())
    item = work_order()
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.staff_repository.has_role = AsyncMock(side_effect=[True, True])
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.user_repository.get_by_id = AsyncMock(return_value=user(30, "customer"))
    service.repository.save = AsyncMock(side_effect=lambda value, activity: value)

    result = await service.assign(
        7, 4, WorkOrderAssignment(assigned_to_id=30), user(20, "customer")
    )

    assert result.assigned_to_id == 30
    activity = service.repository.save.await_args.args[1]
    assert activity.details["assigned_to_id"] == 30


@pytest.mark.asyncio
async def test_assignment_rejects_user_who_is_not_venue_staff():
    service = MaintenanceService(AsyncMock())
    configure_owner(service)
    service.repository.get_for_venue = AsyncMock(return_value=work_order())
    service.user_repository.get_by_id = AsyncMock(return_value=user(30, "customer"))
    service.staff_repository.has_role = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as error:
        await service.assign(7, 4, WorkOrderAssignment(assigned_to_id=30), user())

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_work_order_moves_through_valid_lifecycle():
    service = MaintenanceService(AsyncMock())
    item = work_order(status="in_progress")
    configure_owner(service)
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.save = AsyncMock(side_effect=lambda value, activity: value)

    result = await service.transition(
        7,
        4,
        WorkOrderTransition(status="resolved", note="Fixture replaced"),
        user(),
    )

    assert result.status == "resolved"
    assert result.resolved_at is not None
    activity = service.repository.save.await_args.args[1]
    assert activity.message == "Fixture replaced"
    assert activity.details["previous_status"] == "in_progress"


@pytest.mark.asyncio
async def test_invalid_lifecycle_transition_is_conflict():
    service = MaintenanceService(AsyncMock())
    configure_owner(service)
    service.repository.get_for_venue = AsyncMock(return_value=work_order(status="open"))

    with pytest.raises(HTTPException) as error:
        await service.transition(7, 4, WorkOrderTransition(status="resolved"), user())

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_reopening_resolved_work_order_clears_resolution_time():
    service = MaintenanceService(AsyncMock())
    item = work_order(
        status="resolved", resolved_at=datetime.now(UTC) - timedelta(hours=1)
    )
    configure_owner(service)
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.save = AsyncMock(side_effect=lambda value, activity: value)

    result = await service.transition(
        7, 4, WorkOrderTransition(status="open", note="Issue returned"), user()
    )

    assert result.resolved_at is None


@pytest.mark.asyncio
async def test_staff_comment_is_added_to_immutable_activity_history():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.staff_repository.has_role = AsyncMock(return_value=True)
    service.repository.get_for_venue = AsyncMock(return_value=work_order())
    service.repository.add_activity = AsyncMock(side_effect=lambda activity: activity)

    result = await service.comment(
        7, 4, WorkOrderComment(message="Technician arriving at 14:00"), user(20)
    )

    assert result.work_order_id == 4
    assert result.activity_type == "commented"
    assert result.message == "Technician arriving at 14:00"


@pytest.mark.asyncio
async def test_list_passes_operational_filters_to_repository():
    service = MaintenanceService(AsyncMock())
    configure_owner(service)
    service.repository.list_for_venue = AsyncMock(return_value=[])

    await service.list(
        7,
        user(),
        status="open",
        priority="urgent",
        assigned_to_id=30,
        limit=20,
        offset=40,
    )

    service.repository.list_for_venue.assert_awaited_once_with(
        7,
        status="open",
        priority="urgent",
        assigned_to_id=30,
        limit=20,
        offset=40,
    )
