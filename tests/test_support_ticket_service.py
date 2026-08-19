from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.support_ticket import SupportTicketStatus
from app.schemas.support_ticket import (
    AdminSupportMessageCreate,
    SupportMessageCreate,
    SupportTicketAdminUpdate,
    SupportTicketCreate,
)
from app.services.support_ticket_service import SupportTicketService


def user(user_id=10, role="customer"):
    return MagicMock(id=user_id, role=role, email=f"user{user_id}@example.com")


def ticket(**overrides):
    values = {
        "id": 7,
        "creator_id": 10,
        "assigned_admin_id": None,
        "subject": "Cannot update profile",
        "category": "account",
        "priority": "normal",
        "status": SupportTicketStatus.OPEN.value,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "resolved_at": None,
        "closed_at": None,
    }
    values.update(overrides)
    return MagicMock(**values)


@pytest.mark.asyncio
async def test_ticket_creation_persists_initial_message_atomically():
    service = SupportTicketService(AsyncMock())

    async def create_with_message(created_ticket, message):
        created_ticket.id = 7
        message.id = 1
        message.ticket_id = 7
        return created_ticket, message

    service.ticket_repository.create_with_message = AsyncMock(
        side_effect=create_with_message
    )

    result = await service.create_ticket(
        SupportTicketCreate(
            subject="Cannot update profile",
            category="account",
            message="The save button fails.",
        ),
        user(),
    )

    assert result["id"] == 7
    assert result["status"] == "open"
    assert result["priority"] == "normal"
    assert result["messages"][0].body == "The save button fails."
    assert result["messages"][0].is_internal is False


@pytest.mark.asyncio
async def test_customer_cannot_access_another_users_ticket():
    service = SupportTicketService(AsyncMock())
    service.ticket_repository.get_by_id = AsyncMock(return_value=ticket(creator_id=99))
    service.ticket_repository.get_messages = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.get_ticket(7, user(user_id=10))

    assert error.value.status_code == 403
    service.ticket_repository.get_messages.assert_not_called()


@pytest.mark.asyncio
async def test_customer_detail_excludes_internal_notes():
    service = SupportTicketService(AsyncMock())
    service.ticket_repository.get_by_id = AsyncMock(return_value=ticket())
    service.ticket_repository.get_messages = AsyncMock(return_value=[])

    await service.get_ticket(7, user())

    service.ticket_repository.get_messages.assert_awaited_once_with(
        ticket_id=7, include_internal=False
    )


@pytest.mark.asyncio
async def test_admin_detail_includes_internal_notes():
    service = SupportTicketService(AsyncMock())
    service.ticket_repository.get_by_id = AsyncMock(return_value=ticket())
    service.ticket_repository.get_messages = AsyncMock(return_value=[])

    await service.get_ticket(7, user(user_id=100, role="admin"))

    service.ticket_repository.get_messages.assert_awaited_once_with(
        ticket_id=7, include_internal=True
    )


@pytest.mark.asyncio
async def test_customer_reply_reopens_resolved_ticket_and_notifies_assignee():
    service = SupportTicketService(AsyncMock())
    support_ticket = ticket(
        status=SupportTicketStatus.RESOLVED.value,
        assigned_admin_id=100,
        resolved_at=datetime.now(UTC),
    )
    service.ticket_repository.get_by_id = AsyncMock(return_value=support_ticket)
    service.ticket_repository.create_message = AsyncMock(
        side_effect=lambda message: message
    )
    service.ticket_repository.update = AsyncMock(side_effect=lambda item: item)
    service.notification_service.create_notification = AsyncMock()

    message = await service.add_customer_message(
        7, SupportMessageCreate(message="The issue returned."), user()
    )

    assert message.author_id == 10
    assert support_ticket.status == SupportTicketStatus.OPEN.value
    assert support_ticket.resolved_at is None
    service.notification_service.create_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_closed_ticket_rejects_new_messages():
    service = SupportTicketService(AsyncMock())
    service.ticket_repository.get_by_id = AsyncMock(
        return_value=ticket(status=SupportTicketStatus.CLOSED.value)
    )

    with pytest.raises(HTTPException) as error:
        await service.add_customer_message(
            7, SupportMessageCreate(message="One more thing"), user()
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_admin_public_reply_waits_for_customer_and_notifies_them():
    service = SupportTicketService(AsyncMock())
    support_ticket = ticket()
    service.ticket_repository.get_by_id = AsyncMock(return_value=support_ticket)
    service.ticket_repository.create_message = AsyncMock(
        side_effect=lambda message: message
    )
    service.ticket_repository.update = AsyncMock(side_effect=lambda item: item)
    service.notification_service.create_notification = AsyncMock()

    message = await service.add_admin_message(
        7,
        AdminSupportMessageCreate(message="Please try again.", is_internal=False),
        user(user_id=100, role="admin"),
    )

    assert message.is_internal is False
    assert support_ticket.status == SupportTicketStatus.WAITING_CUSTOMER.value
    service.notification_service.create_notification.assert_awaited_once_with(
        user_id=10,
        title="Support replied to ticket #7",
        message="A support agent added a new response.",
    )


@pytest.mark.asyncio
async def test_internal_note_is_invisible_and_does_not_change_status_or_notify():
    service = SupportTicketService(AsyncMock())
    support_ticket = ticket(status=SupportTicketStatus.IN_PROGRESS.value)
    service.ticket_repository.get_by_id = AsyncMock(return_value=support_ticket)
    service.ticket_repository.create_message = AsyncMock(
        side_effect=lambda message: message
    )
    service.ticket_repository.update = AsyncMock(side_effect=lambda item: item)
    service.notification_service.create_notification = AsyncMock()

    message = await service.add_admin_message(
        7,
        AdminSupportMessageCreate(message="Investigating logs", is_internal=True),
        user(user_id=100, role="admin"),
    )

    assert message.is_internal is True
    assert support_ticket.status == SupportTicketStatus.IN_PROGRESS.value
    service.notification_service.create_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_ticket_can_be_assigned_only_to_admin():
    service = SupportTicketService(AsyncMock())
    service.ticket_repository.get_by_id = AsyncMock(return_value=ticket())
    service.user_repository.get_by_id = AsyncMock(return_value=user(20, "customer"))
    service.ticket_repository.update = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.update_ticket(
            7,
            SupportTicketAdminUpdate(assigned_admin_id=20),
            user(100, "admin"),
        )

    assert error.value.status_code == 400
    service.ticket_repository.update.assert_not_called()


@pytest.mark.asyncio
async def test_resolving_ticket_records_timestamp_priority_and_assignment():
    service = SupportTicketService(AsyncMock())
    support_ticket = ticket()
    service.ticket_repository.get_by_id = AsyncMock(return_value=support_ticket)
    service.user_repository.get_by_id = AsyncMock(return_value=user(100, "admin"))
    service.ticket_repository.update = AsyncMock(side_effect=lambda item: item)
    service.notification_service.create_notification = AsyncMock()

    result = await service.update_ticket(
        7,
        SupportTicketAdminUpdate(
            assigned_admin_id=100,
            priority="high",
            status="resolved",
        ),
        user(100, "admin"),
    )

    assert result.assigned_admin_id == 100
    assert result.priority == "high"
    assert result.status == SupportTicketStatus.RESOLVED.value
    assert result.resolved_at is not None
    assert result.closed_at is None


@pytest.mark.asyncio
async def test_admin_queue_propagates_filters_and_pagination():
    service = SupportTicketService(AsyncMock())
    service.ticket_repository.list_tickets = AsyncMock(return_value=[ticket()])
    service.ticket_repository.count_tickets = AsyncMock(return_value=21)

    result = await service.list_admin_tickets(
        status_filter="open",
        priority_filter="urgent",
        assigned_admin_id=None,
        unassigned_only=True,
        limit=20,
        offset=0,
    )

    assert result["has_next"] is True
    service.ticket_repository.list_tickets.assert_awaited_once_with(
        creator_id=None,
        status="open",
        priority="urgent",
        assigned_admin_id=None,
        unassigned_only=True,
        limit=20,
        offset=0,
    )


def test_empty_admin_update_is_rejected():
    with pytest.raises(ValidationError):
        SupportTicketAdminUpdate()
