from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promotion import Promotion


class PromotionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, promotion: Promotion) -> Promotion:
        self.db.add(promotion)
        await self.db.commit()
        await self.db.refresh(promotion)
        return promotion

    async def get_by_code(self, code: str) -> Promotion | None:
        result = await self.db.execute(
            select(Promotion).where(Promotion.code == code.upper())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, promotion_id: int) -> Promotion | None:
        result = await self.db.execute(
            select(Promotion).where(Promotion.id == promotion_id)
        )
        return result.scalar_one_or_none()

    async def list_for_venue(self, venue_id: int) -> list[Promotion]:
        result = await self.db.execute(
            select(Promotion)
            .where(Promotion.venue_id == venue_id)
            .order_by(Promotion.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, promotion: Promotion) -> Promotion:
        await self.db.commit()
        await self.db.refresh(promotion)
        return promotion
