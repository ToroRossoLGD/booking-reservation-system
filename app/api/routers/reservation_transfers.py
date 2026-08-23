from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.reservation_transfer import (
    ReservationTransferAcceptRead,
    ReservationTransferCreate,
    ReservationTransferRead,
    ReservationTransferToken,
)
from app.services.reservation_transfer_service import ReservationTransferService

router = APIRouter(tags=["Reservation Transfers"])


@router.post(
    "/reservations/{reservation_id}/transfers",
    response_model=ReservationTransferRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation_transfer(
    reservation_id: int,
    data: ReservationTransferCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ReservationTransferService(db).create(
        reservation_id, data, current_user, background_tasks
    )


@router.get(
    "/reservations/{reservation_id}/transfers",
    response_model=list[ReservationTransferRead],
)
async def list_reservation_transfers(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ReservationTransferService(db).list_for_reservation(
        reservation_id, current_user
    )


@router.post(
    "/reservation-transfers/accept",
    response_model=ReservationTransferAcceptRead,
)
async def accept_reservation_transfer(
    data: ReservationTransferToken,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ReservationTransferService(db).accept(
        data.token, current_user, background_tasks
    )


@router.post(
    "/reservation-transfers/decline",
    response_model=ReservationTransferRead,
)
async def decline_reservation_transfer(
    data: ReservationTransferToken,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ReservationTransferService(db).decline(data.token, current_user)


@router.patch(
    "/reservation-transfers/{transfer_id}/revoke",
    response_model=ReservationTransferRead,
)
async def revoke_reservation_transfer(
    transfer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ReservationTransferService(db).revoke(transfer_id, current_user)
