from datetime import UTC, datetime

from sqlalchemy import or_, select
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

    async def list_active(self) -> list[Promotion]:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(Promotion)
            .where(
                Promotion.is_active.is_(True),
                Promotion.valid_from <= now,
                Promotion.valid_until > now,
                or_(
                    Promotion.max_redemptions.is_(None),
                    Promotion.redemption_count < Promotion.max_redemptions,
                ),
            )
            .order_by(Promotion.discount_percent.desc(), Promotion.valid_until)
        )
        return list(result.scalars().all())

    async def update(self, promotion: Promotion) -> Promotion:
        await self.db.commit()
        await self.db.refresh(promotion)
        return promotion
