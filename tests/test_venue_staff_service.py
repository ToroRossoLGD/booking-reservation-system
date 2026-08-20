from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.venue_staff import VenueStaffCreate, VenueStaffUpdate
from app.services.reservation_service import ReservationService
from app.services.venue_staff_service import VenueStaffService


def user(user_id=10, role="owner", email=None):
    return MagicMock(
        id=user_id,
        role=role,
        email=email or f"user{user_id}@example.com",
    )


def venue(owner_id=10):
    return MagicMock(id=7, owner_id=owner_id, name="Central Courts")


def assignment(**overrides):
    values = {
        "id": 4,
        "venue_id": 7,
        "user_id": 20,
        "role": "manager",
        "assigned_at": datetime.now(UTC),
        "assigned_by_id": 10,
        "revoked_at": None,
    }
    values.update(overrides)
    return MagicMock(**values)


@pytest.mark.asyncio
async def test_owner_assigns_existing_user_as_manager():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(
        return_value=user(20, "customer", "staff@example.com")
    )
    service.repository.get_assignment = AsyncMock(return_value=None)
    service.repository.create = AsyncMock(side_effect=lambda item: item)

    result = await service.assign(
        7,
        VenueStaffCreate(email="staff@example.com", role="manager"),
        user(),
    )

    assert result.user_id == 20
    assert result.role == "manager"
    assert result.assigned_by_id == 10


@pytest.mark.asyncio
async def test_owner_cannot_manage_staff_for_another_venue():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))
    service.user_repository.get_by_email = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.assign(
            7,
            VenueStaffCreate(email="staff@example.com", role="manager"),
            user(),
        )

    assert error.value.status_code == 403
    service.user_repository.get_by_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_can_manage_any_venues_staff():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))
    service.user_repository.get_by_email = AsyncMock(return_value=user(20, "customer"))
    service.repository.get_assignment = AsyncMock(return_value=None)
    service.repository.create = AsyncMock(side_effect=lambda item: item)

    result = await service.assign(
        7,
        VenueStaffCreate(email="user20@example.com", role="check_in_agent"),
        user(100, "admin"),
    )

    assert result.role == "check_in_agent"
    assert result.assigned_by_id == 100


@pytest.mark.asyncio
async def test_missing_user_cannot_be_assigned():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.assign(
            7,
            VenueStaffCreate(email="missing@example.com", role="manager"),
            user(),
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_venue_owner_cannot_be_redundantly_assigned():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(return_value=user())

    with pytest.raises(HTTPException) as error:
        await service.assign(
            7,
            VenueStaffCreate(email="user10@example.com", role="manager"),
            user(),
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_active_assignment_is_conflict():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(return_value=user(20, "customer"))
    service.repository.get_assignment = AsyncMock(return_value=assignment())

    with pytest.raises(HTTPException) as error:
        await service.assign(
            7,
            VenueStaffCreate(email="user20@example.com", role="manager"),
            user(),
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_revoked_assignment_can_be_reactivated_with_new_role():
    service = VenueStaffService(AsyncMock())
    revoked = assignment(revoked_at=datetime.now(UTC), role="manager")
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(return_value=user(20, "customer"))
    service.repository.get_assignment = AsyncMock(return_value=revoked)
    service.repository.update = AsyncMock(side_effect=lambda item: item)

    result = await service.assign(
        7,
        VenueStaffCreate(email="user20@example.com", role="check_in_agent"),
        user(),
    )

    assert result.revoked_at is None
    assert result.role == "check_in_agent"


@pytest.mark.asyncio
async def test_owner_updates_staff_role():
    service = VenueStaffService(AsyncMock())
    stored = assignment(role="check_in_agent")
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_active_by_id = AsyncMock(return_value=stored)
    service.repository.update = AsyncMock(side_effect=lambda item: item)

    result = await service.update_role(7, 4, VenueStaffUpdate(role="manager"), user())

    assert result.role == "manager"


@pytest.mark.asyncio
async def test_revocation_is_retained_for_audit():
    service = VenueStaffService(AsyncMock())
    stored = assignment()
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_active_by_id = AsyncMock(return_value=stored)
    service.repository.update = AsyncMock(side_effect=lambda item: item)

    result = await service.revoke(7, 4, user())

    assert result.revoked_at is not None
    service.repository.update.assert_awaited_once_with(stored)


@pytest.mark.asyncio
async def test_staff_member_lists_only_their_active_assignments():
    service = VenueStaffService(AsyncMock())
    service.repository.list_active_for_user = AsyncMock(
        return_value=[{**assignment().__dict__, "venue_name": "Central Courts"}]
    )

    result = await service.list_my_assignments(user(20, "customer"))

    assert result[0]["venue_name"] == "Central Courts"
    service.repository.list_active_for_user.assert_awaited_once_with(20)


@pytest.mark.asyncio
async def test_manager_can_manage_reservation_for_assigned_venue():
    service = ReservationService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=3, venue_id=7)
    )
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.venue_staff_repository.has_role = AsyncMock(return_value=True)

    await service._ensure_owner_can_manage_reservation(
        MagicMock(resource_id=3),
        user(20, "customer"),
        allowed_staff_roles={"manager"},
    )

    service.venue_staff_repository.has_role.assert_awaited_once_with(7, 20, {"manager"})


@pytest.mark.asyncio
async def test_unassigned_user_cannot_manage_reservation():
    service = ReservationService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=3, venue_id=7)
    )
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.venue_staff_repository.has_role = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as error:
        await service._ensure_owner_can_manage_reservation(
            MagicMock(resource_id=3),
            user(30, "customer"),
            allowed_staff_roles={"manager"},
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_check_in_agent_is_not_accepted_for_manager_only_action():
    service = ReservationService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=3, venue_id=7)
    )
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.venue_staff_repository.has_role = AsyncMock(return_value=False)

    with pytest.raises(HTTPException):
        await service._ensure_owner_can_manage_reservation(
            MagicMock(resource_id=3),
            user(20, "customer"),
            allowed_staff_roles={"manager"},
        )

    service.venue_staff_repository.has_role.assert_awaited_once_with(7, 20, {"manager"})
