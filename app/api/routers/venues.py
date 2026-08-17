from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.venue import (
    VenueCancellationPolicyRead,
    VenueCancellationPolicyUpdate,
    VenueCreate,
    VenueListRead,
    VenueRead,
)
from app.services.venue_service import VenueService

router = APIRouter(
    prefix="/venues",
    tags=["Venues"],
)


@router.post("", response_model=VenueRead, status_code=201)
async def create_venue(
    data: VenueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = VenueService(db)
    return await service.create_venue(data, current_user)


@router.get("", response_model=list[VenueRead])
async def get_venues(
    db: AsyncSession = Depends(get_db),
):
    service = VenueService(db)
    return await service.get_all_venues()


@router.get(
    "/search",
    response_model=VenueListRead,
)
async def search_venues(
    q: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    service = VenueService(db)

    return await service.search_venues(
        query_text=q,
        limit=limit,
        offset=offset,
    )


@router.get("/{venue_id}", response_model=VenueRead)
async def get_venue(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = VenueService(db)
    return await service.get_venue_by_id(venue_id)


@router.patch(
    "/{venue_id}/cancellation-policy",
    response_model=VenueCancellationPolicyRead,
)
async def update_cancellation_policy(
    venue_id: int,
    data: VenueCancellationPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = VenueService(db)
    venue = await service.update_cancellation_policy(venue_id, data, current_user)
    return {
        "venue_id": venue.id,
        "free_cancellation_hours": venue.free_cancellation_hours,
        "late_cancellation_refund_percent": (venue.late_cancellation_refund_percent),
    }
