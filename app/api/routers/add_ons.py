from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.add_on import AddOnCreate, AddOnRead, AddOnUpdate
from app.services.add_on_service import AddOnService

router = APIRouter(tags=["Add-ons"])


@router.get("/venues/{venue_id}/add-ons", response_model=list[AddOnRead])
async def list_add_ons(venue_id: int, db: AsyncSession = Depends(get_db)):
    return await AddOnService(db).list_public(venue_id)


@router.get("/venues/{venue_id}/add-ons/manage", response_model=list[AddOnRead])
async def list_managed_add_ons(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await AddOnService(db).list_managed(venue_id, user)


@router.post(
    "/venues/{venue_id}/add-ons",
    response_model=AddOnRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_add_on(
    venue_id: int,
    data: AddOnCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await AddOnService(db).create(venue_id, data, user)


@router.patch("/add-ons/{add_on_id}", response_model=AddOnRead)
async def update_add_on(
    add_on_id: int,
    data: AddOnUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await AddOnService(db).update(add_on_id, data, user)
