from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.reservation import (
    ReservationCreate,
    ReservationRead,
)
from app.services.reservation_service import ReservationService


router = APIRouter(
    prefix="/reservations",
    tags=["Reservations"],
)


@router.post("", response_model=ReservationRead, status_code=201)
async def create_reservation(
    data: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)

    return await service.create_reservation(
        data,
        current_user,
    )


@router.get("/my", response_model=list[ReservationRead])
async def get_my_reservations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)

    return await service.get_my_reservations(
        current_user
    )