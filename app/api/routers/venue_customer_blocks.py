from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.venue_customer_block import (
    MyVenueBlockRead,
    VenueCustomerBlockCreate,
    VenueCustomerBlockRead,
)
from app.services.venue_customer_block_service import VenueCustomerBlockService

router = APIRouter(tags=["Venue Customer Access"])


@router.post(
    "/venues/{venue_id}/customer-blocks",
    response_model=VenueCustomerBlockRead,
    status_code=status.HTTP_201_CREATED,
)
async def block_customer(
    venue_id: int,
    data: VenueCustomerBlockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await VenueCustomerBlockService(db).block(venue_id, data, current_user)


@router.get(
    "/venues/{venue_id}/customer-blocks",
    response_model=list[VenueCustomerBlockRead],
)
async def list_customer_blocks(
    venue_id: int,
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await VenueCustomerBlockService(db).list_for_venue(
        venue_id, active_only, current_user
    )


@router.patch(
    "/venues/{venue_id}/customer-blocks/{block_id}/unblock",
    response_model=VenueCustomerBlockRead,
)
async def unblock_customer(
    venue_id: int,
    block_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await VenueCustomerBlockService(db).unblock(venue_id, block_id, current_user)


@router.get("/venue-customer-blocks/my", response_model=list[MyVenueBlockRead])
async def list_my_venue_blocks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await VenueCustomerBlockService(db).list_my_blocks(current_user)
