import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.reservation_guest import GuestInvitationStatus
from app.schemas.reservation_guest import GuestInvitationCreate
from app.services.reservation_guest_service import ReservationGuestService


def user(user_id=10):
    return MagicMock(id=user_id, role="customer")


def reservation(**overrides):
    values = {"id": 7, "user_id": 10, "status": "confirmed"}
    values.update(overrides)
    return MagicMock(**values)


def invitation(**overrides):
    values = {
        "id": 3,
        "reservation_id": 7,
        "email": "guest@example.com",
        "guest_name": "Guest",
        "status": GuestInvitationStatus.PENDING.value,
        "token_hash": hashlib.sha256(
            b"valid-token-value-that-is-long-enough"
        ).hexdigest(),
        "invited_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "responded_at": None,
    }
    values.update(overrides)
    return MagicMock(**values)


@pytest.mark.asyncio
async def test_invite_stores_hash_and_queues_email_with_plain_token():
    service = ReservationGuestService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())

    async def persist(created):
        created.id = 3
        return created

    service.repository.create = AsyncMock(side_effect=persist)
    tasks = BackgroundTasks()

    result = await service.invite(
        7,
        GuestInvitationCreate(email="GUEST@example.com", guest_name="Guest"),
        user(),
        tasks,
    )

    stored = service.repository.create.await_args.args[0]
    assert stored.email == "guest@example.com"
    emailed_token = (
        tasks.tasks[0].args[2].split("token to accept or decline: ")[1].split("\n")[0]
    )
    assert stored.token_hash == hashlib.sha256(emailed_token.encode()).hexdigest()
    assert stored.token_hash != emailed_token
    assert len(tasks.tasks) == 1
    assert result is stored
    assert emailed_token in tasks.tasks[0].args[2]


@pytest.mark.asyncio
async def test_another_user_cannot_manage_reservation_guests():
    service = ReservationGuestService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.repository.get_for_reservation = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.list_for_reservation(7, user(99))

    assert error.value.status_code == 403
    service.repository.get_for_reservation.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("reservation_status", ["cancelled", "completed", "expired"])
async def test_invitations_are_rejected_for_inactive_reservations(reservation_status):
    service = ReservationGuestService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(status=reservation_status)
    )

    with pytest.raises(HTTPException) as error:
        await service.invite(
            7,
            GuestInvitationCreate(email="guest@example.com", guest_name="Guest"),
            user(),
            BackgroundTasks(),
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_guest_invitation_returns_conflict_and_rolls_back():
    db = AsyncMock()
    service = ReservationGuestService(db)
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.repository.create = AsyncMock(
        side_effect=IntegrityError("insert", {}, Exception("duplicate"))
    )

    with pytest.raises(HTTPException) as error:
        await service.invite(
            7,
            GuestInvitationCreate(email="guest@example.com", guest_name="Guest"),
            user(),
            BackgroundTasks(),
        )

    assert error.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_guest_accepts_with_token_and_token_is_hashed_for_lookup():
    service = ReservationGuestService(AsyncMock())
    pending = invitation()
    service.repository.get_by_hash = AsyncMock(return_value=pending)

    async def persist_response(token_hash, response, responded_at):
        pending.status = response
        pending.responded_at = responded_at
        return pending

    service.repository.respond_if_pending = AsyncMock(side_effect=persist_response)

    result = await service.respond("valid-token-value-that-is-long-enough", "accepted")

    expected_hash = hashlib.sha256(b"valid-token-value-that-is-long-enough").hexdigest()
    service.repository.get_by_hash.assert_awaited_once_with(expected_hash)
    assert result.status == GuestInvitationStatus.ACCEPTED.value
    assert result.responded_at is not None
    service.repository.respond_if_pending.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_invitation_is_gone_and_not_updated():
    service = ReservationGuestService(AsyncMock())
    service.repository.get_by_hash = AsyncMock(
        return_value=invitation(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    service.repository.update = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.respond("expired-token", "declined")

    assert error.value.status_code == 410
    service.repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_used_invitation_cannot_be_replayed():
    service = ReservationGuestService(AsyncMock())
    service.repository.get_by_hash = AsyncMock(
        return_value=invitation(status=GuestInvitationStatus.ACCEPTED.value)
    )

    with pytest.raises(HTTPException) as error:
        await service.respond("used-token", "declined")

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_concurrent_response_loser_gets_conflict():
    service = ReservationGuestService(AsyncMock())
    service.repository.get_by_hash = AsyncMock(return_value=invitation())
    service.repository.respond_if_pending = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.respond("racing-token", "accepted")

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_owner_can_revoke_pending_invitation():
    service = ReservationGuestService(AsyncMock())
    pending = invitation()
    service.repository.get_by_id = AsyncMock(return_value=pending)
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.repository.update = AsyncMock()
    service.repository.update = AsyncMock(side_effect=lambda item: item)

    result = await service.revoke(3, user())

    assert result.status == GuestInvitationStatus.REVOKED.value
    assert result.responded_at is not None


@pytest.mark.asyncio
async def test_only_pending_invitation_can_be_revoked():
    service = ReservationGuestService(AsyncMock())
    service.repository.update = AsyncMock()
    service.repository.get_by_id = AsyncMock(
        return_value=invitation(status=GuestInvitationStatus.DECLINED.value)
    )
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())

    with pytest.raises(HTTPException) as error:
        await service.revoke(3, user())

    assert error.value.status_code == 409
    service.repository.update.assert_not_awaited()
