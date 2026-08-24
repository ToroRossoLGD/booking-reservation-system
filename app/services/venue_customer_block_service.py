from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.venue import Venue
from app.models.venue_customer_block import VenueCustomerBlock
from app.repositories.user_repository import UserRepository
from app.repositories.venue_customer_block_repository import (
    VenueCustomerBlockRepository,
)
from app.repositories.venue_repository import VenueRepository
from app.schemas.venue_customer_block import VenueCustomerBlockCreate


class VenueCustomerBlockService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = VenueCustomerBlockRepository(db)
        self.venue_repository = VenueRepository(db)
        self.user_repository = UserRepository(db)

    async def _manageable_venue(self, venue_id: int, user: User) -> Venue:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if user.role != UserRole.ADMIN.value and venue.owner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can manage customer blocks only for your own venues",
            )
        return venue

    @staticmethod
    def _managed_read(block: VenueCustomerBlock, email: str) -> dict:
        now = datetime.now(UTC)
        return {
            "id": block.id,
            "venue_id": block.venue_id,
            "customer_id": block.customer_id,
            "customer_email": email,
            "reason": block.reason,
            "blocked_at": block.blocked_at,
            "blocked_until": block.blocked_until,
            "blocked_by_id": block.blocked_by_id,
            "unblocked_at": block.unblocked_at,
            "unblocked_by_id": block.unblocked_by_id,
            "is_active": block.unblocked_at is None
            and (block.blocked_until is None or block.blocked_until > now),
        }

    async def block(
        self,
        venue_id: int,
        data: VenueCustomerBlockCreate,
        current_user: User,
    ) -> dict:
        await self._manageable_venue(venue_id, current_user)
        customer = await self.user_repository.get_by_email(str(data.customer_email))
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        if customer.role != UserRole.CUSTOMER.value:
            raise HTTPException(
                status_code=400, detail="Only customer accounts can be blocked"
            )

        now = datetime.now(UTC)
        if data.blocked_until is not None and data.blocked_until <= now:
            raise HTTPException(
                status_code=400, detail="blocked_until must be in the future"
            )

        await self.repository.lock_customer(customer.id)
        block = await self.repository.get(venue_id, customer.id)
        if (
            block is not None
            and block.unblocked_at is None
            and (block.blocked_until is None or block.blocked_until > now)
        ):
            await self.db.rollback()
            raise HTTPException(
                status_code=409, detail="Customer is already blocked for this venue"
            )
        if block is None:
            block = VenueCustomerBlock(
                venue_id=venue_id,
                customer_id=customer.id,
                reason=data.reason,
                blocked_at=now,
                blocked_until=data.blocked_until,
                blocked_by_id=current_user.id,
            )
        else:
            block.reason = data.reason
            block.blocked_at = now
            block.blocked_until = data.blocked_until
            block.blocked_by_id = current_user.id
            block.unblocked_at = None
            block.unblocked_by_id = None
        saved = await self.repository.save(block)
        return self._managed_read(saved, customer.email)

    async def list_for_venue(
        self, venue_id: int, active_only: bool, current_user: User
    ) -> list[dict]:
        await self._manageable_venue(venue_id, current_user)
        rows = await self.repository.list_for_venue(venue_id, active_only)
        return [self._managed_read(block, email) for block, email in rows]

    async def unblock(self, venue_id: int, block_id: int, current_user: User) -> dict:
        await self._manageable_venue(venue_id, current_user)
        block = await self.repository.get_by_id(block_id)
        if block is None or block.venue_id != venue_id:
            raise HTTPException(status_code=404, detail="Customer block not found")
        await self.repository.lock_customer(block.customer_id)
        now = datetime.now(UTC)
        if block.unblocked_at is not None or (
            block.blocked_until is not None and block.blocked_until <= now
        ):
            await self.db.rollback()
            raise HTTPException(status_code=409, detail="Customer block is not active")
        customer = await self.user_repository.get_by_id(block.customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        block.unblocked_at = now
        block.unblocked_by_id = current_user.id
        saved = await self.repository.save(block)
        return self._managed_read(saved, customer.email)

    async def list_my_blocks(self, current_user: User) -> list[dict]:
        rows = await self.repository.list_effective_for_customer(current_user.id)
        return [
            {
                "id": block.id,
                "venue_id": block.venue_id,
                "venue_name": venue_name,
                "reason": block.reason,
                "blocked_at": block.blocked_at,
                "blocked_until": block.blocked_until,
            }
            for block, venue_name in rows
        ]
