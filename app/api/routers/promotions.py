from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.promotion import PromotionCreate, PromotionRead
from app.services.promotion_service import PromotionService

router = APIRouter(tags=["Promotions"])


@router.post(
    "/venues/{venue_id}/promotions",
    response_model=PromotionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_promotion(
    venue_id: int,
    data: PromotionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await PromotionService(db).create_promotion(venue_id, data, current_user)


@router.get("/venues/{venue_id}/promotions", response_model=list[PromotionRead])
async def list_promotions(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await PromotionService(db).list_promotions(venue_id, current_user)


@router.patch("/promotions/{promotion_id}/deactivate", response_model=PromotionRead)
async def deactivate_promotion(
    promotion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await PromotionService(db).deactivate_promotion(promotion_id, current_user)
