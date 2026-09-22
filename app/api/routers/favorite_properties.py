from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, PositiveInt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.property_listing import PropertyListingPage
from app.services.favorite_property_service import FavoritePropertyService

router = APIRouter(prefix="/favorites/properties", tags=["Saved properties"])


class FavoritePropertyStatus(BaseModel):
    property_id: int
    saved: Literal[True]


class FavoritePropertyIds(BaseModel):
    property_ids: list[int]


@router.get("", response_model=PropertyListingPage)
async def saved_properties(
    offset: int = Query(0, ge=0),
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await FavoritePropertyService(db).list(user, offset, limit)


@router.get("/status", response_model=FavoritePropertyIds)
async def status(
    property_ids: Annotated[list[PositiveInt], Query(min_length=1, max_length=50)],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await FavoritePropertyService(db).status(user, property_ids)


@router.put("/{property_id}", response_model=FavoritePropertyStatus)
async def save(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await FavoritePropertyService(db).save(property_id, user)


@router.delete("/{property_id}", status_code=204)
async def remove(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await FavoritePropertyService(db).remove(property_id, user)
