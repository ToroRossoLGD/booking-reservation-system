from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.venue_staff import (
    MyVenueAssignmentRead,
    VenueStaffCreate,
    VenueStaffRead,
    VenueStaffUpdate,
)
from app.services.venue_staff_service import VenueStaffService

router = APIRouter(tags=["Venue Staff"])


@router.post(
    "/venues/{venue_id}/staff",
    response_model=VenueStaffRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_venue_staff(
    venue_id: int,
    data: VenueStaffCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await VenueStaffService(db).assign(venue_id, data, current_user)


@router.get("/venues/{venue_id}/staff", response_model=list[VenueStaffRead])
async def list_venue_staff(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await VenueStaffService(db).list_for_venue(venue_id, current_user)


@router.patch("/venues/{venue_id}/staff/{assignment_id}", response_model=VenueStaffRead)
async def update_venue_staff_role(
    venue_id: int,
    assignment_id: int,
    data: VenueStaffUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await VenueStaffService(db).update_role(
        venue_id, assignment_id, data, current_user
    )


@router.delete(
    "/venues/{venue_id}/staff/{assignment_id}", response_model=VenueStaffRead
)
async def revoke_venue_staff(
    venue_id: int,
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await VenueStaffService(db).revoke(venue_id, assignment_id, current_user)


@router.get("/venue-staff/my", response_model=list[MyVenueAssignmentRead])
async def list_my_venue_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await VenueStaffService(db).list_my_assignments(current_user)
