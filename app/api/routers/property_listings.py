from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.property_listing import (
    OfferType,
    PropertyListingPage,
    PropertyListingRead,
    PropertyListingWrite,
)
from app.services.property_listing_service import PropertyListingService

router = APIRouter(tags=["Property listings"])


@router.get("/properties", response_model=PropertyListingPage)
async def list_properties(
    city: str = Query("", max_length=100),
    offer_type: OfferType | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await PropertyListingService(db).search(
        city=city,
        offer_type=offer_type,
        limit=limit,
        offset=offset,
    )


@router.get("/owner/properties", response_model=PropertyListingPage)
async def owner_properties(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await PropertyListingService(db).search(
        owner_id=user.id,
        limit=limit,
        offset=offset,
    )


@router.get("/properties/{listing_id}", response_model=PropertyListingRead)
async def get_property(listing_id: int, db: AsyncSession = Depends(get_db)):
    return await PropertyListingService(db).get_public(listing_id)


@router.post("/properties", response_model=PropertyListingRead, status_code=201)
async def create_property(
    data: PropertyListingWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await PropertyListingService(db).create(data, user)


@router.put("/properties/{listing_id}", response_model=PropertyListingRead)
async def update_property(
    listing_id: int,
    data: PropertyListingWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await PropertyListingService(db).update(listing_id, data, user)
