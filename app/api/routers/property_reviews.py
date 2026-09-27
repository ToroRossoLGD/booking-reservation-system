from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.property_review import (
    PropertyReviewCreate,
    PropertyReviewPage,
    PropertyReviewRead,
)
from app.services.property_review_service import PropertyReviewService

router = APIRouter(tags=["Property reviews"])


@router.get("/properties/{property_id}/reviews", response_model=PropertyReviewPage)
async def public_reviews(
    property_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await PropertyReviewService(db).public(property_id, offset, limit)


@router.get("/stays/{stay_id}/review", response_model=PropertyReviewRead | None)
async def my_review(
    stay_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PropertyReviewService(db).mine(stay_id, user)


@router.post(
    "/stays/{stay_id}/review", response_model=PropertyReviewRead, status_code=201
)
async def create_review(
    stay_id: int,
    data: PropertyReviewCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PropertyReviewService(db).create(stay_id, data, user)
