from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support_ticket import SupportMessage, SupportTicket


class SupportTicketRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_with_message(
        self, ticket: SupportTicket, message: SupportMessage
    ) -> tuple[SupportTicket, SupportMessage]:
        self.db.add(ticket)
        await self.db.flush()
        message.ticket_id = ticket.id
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(ticket)
        await self.db.refresh(message)
        return ticket, message

    async def get_by_id(self, ticket_id: int) -> SupportTicket | None:
        result = await self.db.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def update(self, ticket: SupportTicket) -> SupportTicket:
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket

    async def create_message(self, message: SupportMessage) -> SupportMessage:
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_messages(
        self, ticket_id: int, include_internal: bool
    ) -> list[SupportMessage]:
        query = select(SupportMessage).where(SupportMessage.ticket_id == ticket_id)
        if not include_internal:
            query = query.where(SupportMessage.is_internal.is_(False))
        result = await self.db.execute(query.order_by(SupportMessage.created_at))
        return list(result.scalars().all())

    async def list_tickets(
        self,
        creator_id: int | None,
        status: str | None,
        priority: str | None,
        assigned_admin_id: int | None,
        unassigned_only: bool,
        limit: int,
        offset: int,
    ) -> list[SupportTicket]:
        query = self._filtered_query(
            creator_id, status, priority, assigned_admin_id, unassigned_only
        )
        result = await self.db.execute(
            query.order_by(SupportTicket.updated_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def count_tickets(
        self,
        creator_id: int | None,
        status: str | None,
        priority: str | None,
        assigned_admin_id: int | None,
        unassigned_only: bool,
    ) -> int:
        query = self._filtered_query(
            creator_id,
            status,
            priority,
            assigned_admin_id,
            unassigned_only,
            count=True,
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    @staticmethod
    def _filtered_query(
        creator_id: int | None,
        status: str | None,
        priority: str | None,
        assigned_admin_id: int | None,
        unassigned_only: bool,
        count: bool = False,
    ):
        query = select(func.count(SupportTicket.id)) if count else select(SupportTicket)
        if creator_id is not None:
            query = query.where(SupportTicket.creator_id == creator_id)
        if status is not None:
            query = query.where(SupportTicket.status == status)
        if priority is not None:
            query = query.where(SupportTicket.priority == priority)
        if unassigned_only:
            query = query.where(SupportTicket.assigned_admin_id.is_(None))
        elif assigned_admin_id is not None:
            query = query.where(SupportTicket.assigned_admin_id == assigned_admin_id)
        return query
