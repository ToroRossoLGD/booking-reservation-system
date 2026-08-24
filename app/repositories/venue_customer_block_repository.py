from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.venue import Venue
from app.models.venue_customer_block import VenueCustomerBlock


class VenueCustomerBlockRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def lock_customer(self, customer_id: int) -> None:
        await self.db.execute(
            select(User.id).where(User.id == customer_id).with_for_update()
        )

    async def get(self, venue_id: int, customer_id: int) -> VenueCustomerBlock | None:
        result = await self.db.execute(
            select(VenueCustomerBlock).where(
                VenueCustomerBlock.venue_id == venue_id,
                VenueCustomerBlock.customer_id == customer_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, block_id: int) -> VenueCustomerBlock | None:
        result = await self.db.execute(
            select(VenueCustomerBlock).where(VenueCustomerBlock.id == block_id)
        )
        return result.scalar_one_or_none()

    async def get_effective(
        self, venue_id: int, customer_id: int, now: datetime | None = None
    ) -> VenueCustomerBlock | None:
        effective_at = now or datetime.now(UTC)
        result = await self.db.execute(
            select(VenueCustomerBlock).where(
                VenueCustomerBlock.venue_id == venue_id,
                VenueCustomerBlock.customer_id == customer_id,
                VenueCustomerBlock.unblocked_at.is_(None),
                or_(
                    VenueCustomerBlock.blocked_until.is_(None),
                    VenueCustomerBlock.blocked_until > effective_at,
                ),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_venue(
        self, venue_id: int, active_only: bool
    ) -> list[tuple[VenueCustomerBlock, str]]:
        query = (
            select(VenueCustomerBlock, User.email)
            .join(User, User.id == VenueCustomerBlock.customer_id)
            .where(VenueCustomerBlock.venue_id == venue_id)
        )
        if active_only:
            now = datetime.now(UTC)
            query = query.where(
                VenueCustomerBlock.unblocked_at.is_(None),
                or_(
                    VenueCustomerBlock.blocked_until.is_(None),
                    VenueCustomerBlock.blocked_until > now,
                ),
            )
        result = await self.db.execute(
            query.order_by(VenueCustomerBlock.blocked_at.desc())
        )
        return list(result.all())

    async def list_effective_for_customer(
        self, customer_id: int
    ) -> list[tuple[VenueCustomerBlock, str]]:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(VenueCustomerBlock, Venue.name)
            .join(Venue, Venue.id == VenueCustomerBlock.venue_id)
            .where(
                VenueCustomerBlock.customer_id == customer_id,
                VenueCustomerBlock.unblocked_at.is_(None),
                or_(
                    VenueCustomerBlock.blocked_until.is_(None),
                    VenueCustomerBlock.blocked_until > now,
                ),
            )
            .order_by(Venue.name)
        )
        return list(result.all())

    async def save(self, block: VenueCustomerBlock) -> VenueCustomerBlock:
        self.db.add(block)
        await self.db.commit()
        await self.db.refresh(block)
        return block
