from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.support_ticket import (
    AdminSupportMessageCreate,
    SupportMessageCreate,
    SupportMessageRead,
    SupportTicketAdminUpdate,
    SupportTicketCreate,
    SupportTicketDetailRead,
    SupportTicketListRead,
    SupportTicketRead,
)
from app.services.support_ticket_service import SupportTicketService

router = APIRouter(prefix="/support", tags=["Customer Support"])


@router.post(
    "/tickets",
    response_model=SupportTicketDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_support_ticket(
    data: SupportTicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await SupportTicketService(db).create_ticket(data, current_user)


@router.get("/tickets/my", response_model=SupportTicketListRead)
async def list_my_support_tickets(
    ticket_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await SupportTicketService(db).list_my_tickets(
        current_user, ticket_status, limit, offset
    )


@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetailRead)
async def get_support_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await SupportTicketService(db).get_ticket(ticket_id, current_user)


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=SupportMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_support_message(
    ticket_id: int,
    data: SupportMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await SupportTicketService(db).add_customer_message(
        ticket_id, data, current_user
    )


@router.patch("/tickets/{ticket_id}/close", response_model=SupportTicketRead)
async def close_support_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await SupportTicketService(db).close_my_ticket(ticket_id, current_user)


@router.get("/admin/tickets", response_model=SupportTicketListRead)
async def list_admin_support_tickets(
    ticket_status: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    assigned_admin_id: int | None = None,
    unassigned_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    return await SupportTicketService(db).list_admin_tickets(
        ticket_status,
        priority,
        assigned_admin_id,
        unassigned_only,
        limit,
        offset,
    )


@router.patch("/admin/tickets/{ticket_id}", response_model=SupportTicketRead)
async def update_admin_support_ticket(
    ticket_id: int,
    data: SupportTicketAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    return await SupportTicketService(db).update_ticket(ticket_id, data, current_user)


@router.post(
    "/admin/tickets/{ticket_id}/messages",
    response_model=SupportMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_admin_support_message(
    ticket_id: int,
    data: AdminSupportMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    return await SupportTicketService(db).add_admin_message(
        ticket_id, data, current_user
    )
