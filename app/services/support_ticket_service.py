from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support_ticket import (
    SupportMessage,
    SupportTicket,
    SupportTicketPriority,
    SupportTicketStatus,
)
from app.models.user import User
from app.repositories.support_ticket_repository import SupportTicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.support_ticket import (
    AdminSupportMessageCreate,
    SupportMessageCreate,
    SupportTicketAdminUpdate,
    SupportTicketCreate,
)
from app.services.notification_service import NotificationService


class SupportTicketService:
    def __init__(self, db: AsyncSession):
        self.ticket_repository = SupportTicketRepository(db)
        self.user_repository = UserRepository(db)
        self.notification_service = NotificationService(db)

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=400, detail="limit must be between 1 and 100"
            )
        if offset < 0:
            raise HTTPException(status_code=400, detail="offset must be non-negative")

    @staticmethod
    def _list_result(items, total: int, limit: int, offset: int) -> dict:
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
        }

    async def create_ticket(
        self, data: SupportTicketCreate, current_user: User
    ) -> dict:
        now = datetime.now(UTC)
        ticket = SupportTicket(
            creator_id=current_user.id,
            subject=data.subject,
            category=data.category,
            priority=SupportTicketPriority.NORMAL.value,
            status=SupportTicketStatus.OPEN.value,
            created_at=now,
            updated_at=now,
        )
        message = SupportMessage(
            author_id=current_user.id,
            body=data.message,
            is_internal=False,
            created_at=now,
        )
        ticket, message = await self.ticket_repository.create_with_message(
            ticket, message
        )
        return {**self._ticket_detail(ticket, [message])}

    async def list_my_tickets(
        self,
        current_user: User,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        self._validate_pagination(limit, offset)
        self._validate_status(status_filter)
        filters = dict(
            creator_id=current_user.id,
            status=status_filter,
            priority=None,
            assigned_admin_id=None,
            unassigned_only=False,
        )
        items = await self.ticket_repository.list_tickets(
            **filters, limit=limit, offset=offset
        )
        total = await self.ticket_repository.count_tickets(**filters)
        return self._list_result(items, total, limit, offset)

    async def list_admin_tickets(
        self,
        status_filter: str | None,
        priority_filter: str | None,
        assigned_admin_id: int | None,
        unassigned_only: bool,
        limit: int,
        offset: int,
    ) -> dict:
        self._validate_pagination(limit, offset)
        self._validate_status(status_filter)
        if priority_filter is not None and priority_filter not in {
            item.value for item in SupportTicketPriority
        }:
            raise HTTPException(status_code=400, detail="Invalid ticket priority")
        filters = dict(
            creator_id=None,
            status=status_filter,
            priority=priority_filter,
            assigned_admin_id=assigned_admin_id,
            unassigned_only=unassigned_only,
        )
        items = await self.ticket_repository.list_tickets(
            **filters, limit=limit, offset=offset
        )
        total = await self.ticket_repository.count_tickets(**filters)
        return self._list_result(items, total, limit, offset)

    async def get_ticket(self, ticket_id: int, current_user: User) -> dict:
        ticket = await self._get_accessible_ticket(ticket_id, current_user)
        messages = await self.ticket_repository.get_messages(
            ticket_id=ticket.id,
            include_internal=current_user.role == "admin",
        )
        return self._ticket_detail(ticket, messages)

    async def add_customer_message(
        self,
        ticket_id: int,
        data: SupportMessageCreate,
        current_user: User,
    ) -> SupportMessage:
        ticket = await self._get_accessible_ticket(ticket_id, current_user)
        if current_user.role == "admin":
            raise HTTPException(
                status_code=400, detail="Use the admin message endpoint"
            )
        self._ensure_ticket_accepts_messages(ticket)
        now = datetime.now(UTC)
        message = await self.ticket_repository.create_message(
            SupportMessage(
                ticket_id=ticket.id,
                author_id=current_user.id,
                body=data.message,
                is_internal=False,
                created_at=now,
            )
        )
        if ticket.status in {
            SupportTicketStatus.RESOLVED.value,
            SupportTicketStatus.WAITING_CUSTOMER.value,
        }:
            ticket.status = SupportTicketStatus.OPEN.value
            ticket.resolved_at = None
        ticket.updated_at = now
        await self.ticket_repository.update(ticket)
        if ticket.assigned_admin_id is not None:
            await self.notification_service.create_notification(
                user_id=ticket.assigned_admin_id,
                title=f"Support ticket #{ticket.id} updated",
                message="The customer added a new message.",
            )
        return message

    async def add_admin_message(
        self,
        ticket_id: int,
        data: AdminSupportMessageCreate,
        current_user: User,
    ) -> SupportMessage:
        ticket = await self._get_required_ticket(ticket_id)
        self._ensure_ticket_accepts_messages(ticket)
        now = datetime.now(UTC)
        message = await self.ticket_repository.create_message(
            SupportMessage(
                ticket_id=ticket.id,
                author_id=current_user.id,
                body=data.message,
                is_internal=data.is_internal,
                created_at=now,
            )
        )
        ticket.updated_at = now
        if not data.is_internal:
            ticket.status = SupportTicketStatus.WAITING_CUSTOMER.value
            await self.notification_service.create_notification(
                user_id=ticket.creator_id,
                title=f"Support replied to ticket #{ticket.id}",
                message="A support agent added a new response.",
            )
        await self.ticket_repository.update(ticket)
        return message

    async def close_my_ticket(
        self, ticket_id: int, current_user: User
    ) -> SupportTicket:
        ticket = await self._get_accessible_ticket(ticket_id, current_user)
        if ticket.creator_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You can close only your own tickets"
            )
        if ticket.status == SupportTicketStatus.CLOSED.value:
            return ticket
        now = datetime.now(UTC)
        ticket.status = SupportTicketStatus.CLOSED.value
        ticket.closed_at = now
        ticket.updated_at = now
        return await self.ticket_repository.update(ticket)

    async def update_ticket(
        self,
        ticket_id: int,
        data: SupportTicketAdminUpdate,
        current_user: User,
    ) -> SupportTicket:
        ticket = await self._get_required_ticket(ticket_id)
        now = datetime.now(UTC)
        if "assigned_admin_id" in data.model_fields_set:
            if data.assigned_admin_id is not None:
                assigned_user = await self.user_repository.get_by_id(
                    data.assigned_admin_id
                )
                if assigned_user is None or assigned_user.role != "admin":
                    raise HTTPException(
                        status_code=400,
                        detail="Tickets can be assigned only to administrators",
                    )
            ticket.assigned_admin_id = data.assigned_admin_id
        if data.priority is not None:
            ticket.priority = data.priority
        if data.status is not None:
            ticket.status = data.status
            ticket.resolved_at = (
                now if data.status == SupportTicketStatus.RESOLVED.value else None
            )
            ticket.closed_at = (
                now if data.status == SupportTicketStatus.CLOSED.value else None
            )
        ticket.updated_at = now
        updated = await self.ticket_repository.update(ticket)
        await self.notification_service.create_notification(
            user_id=ticket.creator_id,
            title=f"Support ticket #{ticket.id} updated",
            message=f"Your ticket status is now {ticket.status}.",
        )
        return updated

    async def _get_required_ticket(self, ticket_id: int) -> SupportTicket:
        ticket = await self.ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Support ticket not found")
        return ticket

    async def _get_accessible_ticket(
        self, ticket_id: int, current_user: User
    ) -> SupportTicket:
        ticket = await self._get_required_ticket(ticket_id)
        if current_user.role != "admin" and ticket.creator_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can access only your own support tickets",
            )
        return ticket

    @staticmethod
    def _ensure_ticket_accepts_messages(ticket: SupportTicket) -> None:
        if ticket.status == SupportTicketStatus.CLOSED.value:
            raise HTTPException(
                status_code=409, detail="Closed tickets cannot be updated"
            )

    @staticmethod
    def _validate_status(status_filter: str | None) -> None:
        if status_filter is not None and status_filter not in {
            item.value for item in SupportTicketStatus
        }:
            raise HTTPException(status_code=400, detail="Invalid ticket status")

    @staticmethod
    def _ticket_detail(ticket: SupportTicket, messages: list[SupportMessage]) -> dict:
        return {
            "id": ticket.id,
            "creator_id": ticket.creator_id,
            "assigned_admin_id": ticket.assigned_admin_id,
            "subject": ticket.subject,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "resolved_at": ticket.resolved_at,
            "closed_at": ticket.closed_at,
            "messages": messages,
        }
