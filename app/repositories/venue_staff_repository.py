from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.models.venue_staff import VenueStaff


class VenueStaffRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_assignment(self, venue_id: int, user_id: int) -> VenueStaff | None:
        result = await self.db.execute(
            select(VenueStaff).where(
                VenueStaff.venue_id == venue_id,
                VenueStaff.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_id(
        self, venue_id: int, assignment_id: int
    ) -> VenueStaff | None:
        result = await self.db.execute(
            select(VenueStaff).where(
                VenueStaff.id == assignment_id,
                VenueStaff.venue_id == venue_id,
                VenueStaff.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, assignment: VenueStaff) -> VenueStaff:
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def update(self, assignment: VenueStaff) -> VenueStaff:
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def list_active_for_venue(self, venue_id: int) -> list[VenueStaff]:
        result = await self.db.execute(
            select(VenueStaff)
            .where(
                VenueStaff.venue_id == venue_id,
                VenueStaff.revoked_at.is_(None),
            )
            .order_by(VenueStaff.assigned_at, VenueStaff.id)
        )
        return list(result.scalars().all())

    async def list_active_for_user(self, user_id: int) -> list[dict]:
        result = await self.db.execute(
            select(VenueStaff, Venue.name)
            .join(Venue, Venue.id == VenueStaff.venue_id)
            .where(
                VenueStaff.user_id == user_id,
                VenueStaff.revoked_at.is_(None),
            )
            .order_by(Venue.name, VenueStaff.id)
        )
        return [
            {**assignment.__dict__, "venue_name": venue_name}
            for assignment, venue_name in result.all()
        ]

    async def has_role(
        self, venue_id: int, user_id: int, allowed_roles: set[str]
    ) -> bool:
        result = await self.db.execute(
            select(VenueStaff.id).where(
                VenueStaff.venue_id == venue_id,
                VenueStaff.user_id == user_id,
                VenueStaff.role.in_(allowed_roles),
                VenueStaff.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None
