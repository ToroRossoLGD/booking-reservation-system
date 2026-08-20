from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.reservation_guest import (
    GuestInvitationCreate,
    GuestInvitationRead,
    GuestInvitationResponse,
)
from app.services.reservation_guest_service import ReservationGuestService

router = APIRouter(tags=["Reservation Guests"])


@router.post(
    "/reservations/{reservation_id}/guest-invitations",
    response_model=GuestInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_guest(
    reservation_id: int,
    data: GuestInvitationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ReservationGuestService(db).invite(
        reservation_id, data, current_user, background_tasks
    )


@router.get(
    "/reservations/{reservation_id}/guest-invitations",
    response_model=list[GuestInvitationRead],
)
async def list_guest_invitations(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ReservationGuestService(db).list_for_reservation(
        reservation_id, current_user
    )


@router.post("/guest-invitations/respond", response_model=GuestInvitationRead)
async def respond_to_guest_invitation(
    data: GuestInvitationResponse, db: AsyncSession = Depends(get_db)
):
    return await ReservationGuestService(db).respond(data.token, data.response)


@router.patch(
    "/guest-invitations/{invitation_id}/revoke", response_model=GuestInvitationRead
)
async def revoke_guest_invitation(
    invitation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ReservationGuestService(db).revoke(invitation_id, current_user)
