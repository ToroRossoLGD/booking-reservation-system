from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promotion import Promotion
from app.models.user import User
from app.repositories.promotion_repository import PromotionRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.promotion import PromotionCreate


class PromotionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.promotion_repository = PromotionRepository(db)
        self.venue_repository = VenueRepository(db)

    async def _ensure_venue_access(self, venue_id: int, current_user: User) -> None:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if current_user.role != "admin" and venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can manage promotions only for your own venues",
            )

    async def create_promotion(
        self, venue_id: int, data: PromotionCreate, current_user: User
    ) -> Promotion:
        await self._ensure_venue_access(venue_id, current_user)
        if data.valid_from.tzinfo is None or data.valid_until.tzinfo is None:
            raise HTTPException(
                status_code=400, detail="Promotion times must include a timezone"
            )
        if data.valid_from >= data.valid_until:
            raise HTTPException(
                status_code=400, detail="valid_from must be before valid_until"
            )
        if data.valid_until <= datetime.now(UTC):
            raise HTTPException(
                status_code=400, detail="Promotion must end in the future"
            )

        promotion = Promotion(
            code=data.code,
            venue_id=venue_id,
            discount_percent=data.discount_percent,
            valid_from=data.valid_from,
            valid_until=data.valid_until,
            max_redemptions=data.max_redemptions,
        )
        try:
            return await self.promotion_repository.create(promotion)
        except IntegrityError as error:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Promotion code already exists",
            ) from error

    async def list_promotions(
        self, venue_id: int, current_user: User
    ) -> list[Promotion]:
        await self._ensure_venue_access(venue_id, current_user)
        return await self.promotion_repository.list_for_venue(venue_id)

    async def list_active_promotions(self) -> list[Promotion]:
        return await self.promotion_repository.list_active()

    async def deactivate_promotion(
        self, promotion_id: int, current_user: User
    ) -> Promotion:
        promotion = await self.promotion_repository.get_by_id(promotion_id)
        if promotion is None:
            raise HTTPException(status_code=404, detail="Promotion not found")
        await self._ensure_venue_access(promotion.venue_id, current_user)
        promotion.is_active = False
        return await self.promotion_repository.update(promotion)
