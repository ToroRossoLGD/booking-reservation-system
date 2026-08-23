from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.reservation_event import ReservationEventType
from app.models.reservation_transfer import (
    ReservationTransfer,
    ReservationTransferStatus,
)
from app.schemas.reservation_transfer import ReservationTransferCreate
from app.services.reservation_transfer_service import ReservationTransferService


def user(user_id=10, email="sender@example.com", role="customer"):
    return MagicMock(id=user_id, email=email, role=role)


def reservation(**changes):
    values = {
        "id": 4,
        "user_id": 10,
        "resource_id": 8,
        "status": "confirmed",
        "start_time": datetime.now(UTC) + timedelta(days=2),
    }
    values.update(changes)
    return MagicMock(**values)


def transfer(**changes):
    values = {
        "id": 6,
        "reservation_id": 4,
        "previous_owner_id": 10,
        "recipient_user_id": None,
        "recipient_email": "recipient@example.com",
        "status": "pending",
        "token_hash": "a" * 64,
        "active_key": "4",
        "message": None,
        "created_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(hours=24),
        "responded_at": None,
    }
    values.update(changes)
    return MagicMock(**values)


def configure_recipient_capacity(service, active_count=0, maximum=10):
    service.reservation_repository.lock_user_for_booking_rules = AsyncMock()
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=8, venue_id=7)
    )
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=7, max_active_reservations_per_customer=maximum)
    )
    service.reservation_repository.count_active_for_user_at_venue = AsyncMock(
        return_value=active_count
    )


@pytest.mark.asyncio
async def test_owner_creates_secure_expiring_transfer_and_queues_email():
    service = ReservationTransferService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.repository.expire_pending = AsyncMock()
    service.repository.create = AsyncMock(side_effect=lambda item: item)
    service.email_service.send_email = MagicMock()
    tasks = BackgroundTasks()

    result = await service.create(
        4,
        ReservationTransferCreate(
            recipient_email="Recipient@Example.com", message="Enjoy the booking"
        ),
        user(),
        tasks,
    )

    assert isinstance(result, ReservationTransfer)
    assert result.recipient_email == "recipient@example.com"
    assert result.status == ReservationTransferStatus.PENDING.value
    assert result.token_hash != ""
    assert result.active_key == "4"
    assert len(tasks.tasks) == 1


@pytest.mark.asyncio
async def test_transfer_requires_reservation_owner():
    service = ReservationTransferService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(user_id=99)
    )

    with pytest.raises(HTTPException) as error:
        await service.create(
            4,
            ReservationTransferCreate(recipient_email="recipient@example.com"),
            user(),
            BackgroundTasks(),
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "cancelled", "completed", "expired"])
async def test_only_confirmed_reservations_can_be_transferred(status):
    service = ReservationTransferService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(status=status)
    )

    with pytest.raises(HTTPException) as error:
        await service.create(
            4,
            ReservationTransferCreate(recipient_email="recipient@example.com"),
            user(),
            BackgroundTasks(),
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_started_reservation_cannot_be_transferred():
    service = ReservationTransferService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(start_time=datetime.now(UTC) - timedelta(minutes=1))
    )

    with pytest.raises(HTTPException) as error:
        await service.create(
            4,
            ReservationTransferCreate(recipient_email="recipient@example.com"),
            user(),
            BackgroundTasks(),
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_self_transfer_is_rejected_case_insensitively():
    service = ReservationTransferService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())

    with pytest.raises(HTTPException) as error:
        await service.create(
            4,
            ReservationTransferCreate(recipient_email="SENDER@example.com"),
            user(),
            BackgroundTasks(),
        )

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_second_pending_transfer_is_conflict():
    db = AsyncMock()
    service = ReservationTransferService(db)
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.repository.expire_pending = AsyncMock()
    service.repository.create = AsyncMock(side_effect=IntegrityError("x", {}, None))

    with pytest.raises(HTTPException) as error:
        await service.create(
            4,
            ReservationTransferCreate(recipient_email="recipient@example.com"),
            user(),
            BackgroundTasks(),
        )

    assert error.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_intended_recipient_accepts_and_ownership_changes_atomically():
    service = ReservationTransferService(AsyncMock())
    invitation = transfer()
    item = reservation()
    service.repository.get_by_hash_for_update = AsyncMock(return_value=invitation)
    service.reservation_repository.get_by_id_for_update = AsyncMock(return_value=item)
    configure_recipient_capacity(service)
    service.repository.complete = AsyncMock(side_effect=lambda t, r, event: t)
    service.notification_service.create_notification = AsyncMock()
    recipient = user(20, "recipient@example.com")

    result = await service.accept("x" * 32, recipient)

    assert item.user_id == 20
    assert invitation.status == ReservationTransferStatus.ACCEPTED.value
    assert invitation.active_key is None
    assert result["previous_owner_id"] == 10
    assert result["new_owner_id"] == 20
    event = service.repository.complete.await_args.args[2]
    assert event.event_type == ReservationEventType.TRANSFERRED.value
    assert event.details["transfer_id"] == 6


@pytest.mark.asyncio
async def test_transfer_cannot_bypass_recipient_active_booking_limit():
    db = AsyncMock()
    service = ReservationTransferService(db)
    service.repository.get_by_hash_for_update = AsyncMock(return_value=transfer())
    service.reservation_repository.get_by_id_for_update = AsyncMock(
        return_value=reservation()
    )
    configure_recipient_capacity(service, active_count=3, maximum=3)

    with pytest.raises(HTTPException) as error:
        await service.accept("x" * 32, user(20, "recipient@example.com"))

    assert error.value.status_code == 409
    assert "active reservation limit" in error.value.detail
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticated_email_must_match_invitation():
    db = AsyncMock()
    service = ReservationTransferService(db)
    service.repository.get_by_hash_for_update = AsyncMock(return_value=transfer())

    with pytest.raises(HTTPException) as error:
        await service.accept("x" * 32, user(20, "attacker@example.com"))

    assert error.value.status_code == 403
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_invitation_is_closed_and_returns_gone():
    service = ReservationTransferService(AsyncMock())
    invitation = transfer(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    service.repository.get_by_hash_for_update = AsyncMock(return_value=invitation)
    service.repository.save = AsyncMock(side_effect=lambda item: item)

    with pytest.raises(HTTPException) as error:
        await service.accept("x" * 32, user(20, "recipient@example.com"))

    assert error.value.status_code == 410
    assert invitation.status == ReservationTransferStatus.EXPIRED.value
    assert invitation.active_key is None


@pytest.mark.asyncio
async def test_transfer_fails_if_ownership_changed_before_acceptance():
    db = AsyncMock()
    service = ReservationTransferService(db)
    service.repository.get_by_hash_for_update = AsyncMock(return_value=transfer())
    service.reservation_repository.get_by_id_for_update = AsyncMock(
        return_value=reservation(user_id=30)
    )

    with pytest.raises(HTTPException) as error:
        await service.accept("x" * 32, user(20, "recipient@example.com"))

    assert error.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_recipient_can_decline_pending_transfer():
    service = ReservationTransferService(AsyncMock())
    invitation = transfer()
    service.repository.get_by_hash_for_update = AsyncMock(return_value=invitation)
    service.repository.save = AsyncMock(side_effect=lambda item: item)

    result = await service.decline("x" * 32, user(20, "recipient@example.com"))

    assert result.status == ReservationTransferStatus.DECLINED.value
    assert result.recipient_user_id == 20
    assert result.active_key is None


@pytest.mark.asyncio
async def test_sender_can_revoke_pending_transfer():
    service = ReservationTransferService(AsyncMock())
    invitation = transfer()
    service.repository.get_by_id = AsyncMock(return_value=invitation)
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.repository.save = AsyncMock(side_effect=lambda item: item)

    result = await service.revoke(6, user())

    assert result.status == ReservationTransferStatus.REVOKED.value
    assert result.active_key is None


@pytest.mark.asyncio
async def test_non_pending_transfer_cannot_be_revoked():
    service = ReservationTransferService(AsyncMock())
    service.repository.get_by_id = AsyncMock(return_value=transfer(status="accepted"))
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())

    with pytest.raises(HTTPException) as error:
        await service.revoke(6, user())

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_listing_expires_stale_pending_offers_first():
    service = ReservationTransferService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.repository.expire_pending = AsyncMock()
    service.repository.list_for_reservation = AsyncMock(return_value=[])

    result = await service.list_for_reservation(4, user())

    assert result == []
    service.repository.expire_pending.assert_awaited_once()


@pytest.mark.asyncio
async def test_former_owner_sees_only_transfers_they_initiated():
    service = ReservationTransferService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(user_id=30)
    )
    own = transfer(previous_owner_id=10)
    later = transfer(id=9, previous_owner_id=30)
    service.repository.list_for_reservation = AsyncMock(return_value=[later, own])
    service.repository.expire_pending = AsyncMock()

    result = await service.list_for_reservation(4, user())

    assert result == [own]
    service.repository.expire_pending.assert_not_awaited()


@pytest.mark.asyncio
async def test_unrelated_user_cannot_view_transfer_history():
    service = ReservationTransferService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(user_id=30)
    )
    service.repository.list_for_reservation = AsyncMock(return_value=[transfer()])

    with pytest.raises(HTTPException) as error:
        await service.list_for_reservation(4, user(40, "other@example.com"))

    assert error.value.status_code == 403
