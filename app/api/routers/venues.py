from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.venue import VenueCreate, VenueRead
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


@router.get("/{venue_id}", response_model=VenueRead)
async def get_venue(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = VenueService(db)
    return await service.get_venue_by_id(venue_id)