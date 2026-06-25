from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.owner import (
    OwnerReservationRead,
    OwnerResourceRead,
    OwnerStatsRead,
    OwnerVenueRead,
)
from app.services.owner_service import OwnerService

router = APIRouter(
    prefix="/owner",
    tags=["Owner Dashboard"],
)


@router.get(
    "/venues",
    response_model=list[OwnerVenueRead],
)
async def get_owner_venues(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = OwnerService(db)

    return await service.get_my_venues(current_user)


@router.get(
    "/resources",
    response_model=list[OwnerResourceRead],
)
async def get_owner_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = OwnerService(db)

    return await service.get_my_resources(current_user)


@router.get(
    "/reservations",
    response_model=list[OwnerReservationRead],
)
async def get_owner_reservations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = OwnerService(db)

    return await service.get_my_reservations(current_user)


@router.get(
    "/stats",
    response_model=OwnerStatsRead,
)
async def get_owner_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = OwnerService(db)

    return await service.get_owner_stats(current_user=current_user)
