from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.venue import Venue
from app.models.venue_staff import VenueStaff
from app.repositories.user_repository import UserRepository
from app.repositories.venue_repository import VenueRepository
from app.repositories.venue_staff_repository import VenueStaffRepository
from app.schemas.venue_staff import VenueStaffCreate, VenueStaffUpdate


class VenueStaffService:
    def __init__(self, db: AsyncSession):
        self.repository = VenueStaffRepository(db)
        self.venue_repository = VenueRepository(db)
        self.user_repository = UserRepository(db)

    async def _manageable_venue(self, venue_id: int, user: User) -> Venue:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if user.role != "admin" and venue.owner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can manage staff only for your own venues",
            )
        return venue

    async def assign(
        self, venue_id: int, data: VenueStaffCreate, current_user: User
    ) -> VenueStaff:
        venue = await self._manageable_venue(venue_id, current_user)
        staff_user = await self.user_repository.get_by_email(str(data.email))
        if staff_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if staff_user.id == venue.owner_id:
            raise HTTPException(
                status_code=409, detail="The venue owner already has full access"
            )

        now = datetime.now(UTC)
        assignment = await self.repository.get_assignment(venue_id, staff_user.id)
        if assignment is None:
            return await self.repository.create(
                VenueStaff(
                    venue_id=venue_id,
                    user_id=staff_user.id,
                    role=data.role,
                    assigned_at=now,
                    assigned_by_id=current_user.id,
                )
            )
        if assignment.revoked_at is None:
            raise HTTPException(status_code=409, detail="User is already venue staff")
        assignment.role = data.role
        assignment.assigned_at = now
        assignment.assigned_by_id = current_user.id
        assignment.revoked_at = None
        return await self.repository.update(assignment)

    async def list_for_venue(
        self, venue_id: int, current_user: User
    ) -> list[VenueStaff]:
        await self._manageable_venue(venue_id, current_user)
        return await self.repository.list_active_for_venue(venue_id)

    async def list_my_assignments(self, current_user: User) -> list[dict]:
        return await self.repository.list_active_for_user(current_user.id)

    async def update_role(
        self,
        venue_id: int,
        assignment_id: int,
        data: VenueStaffUpdate,
        current_user: User,
    ) -> VenueStaff:
        await self._manageable_venue(venue_id, current_user)
        assignment = await self._active_assignment(venue_id, assignment_id)
        assignment.role = data.role
        return await self.repository.update(assignment)

    async def revoke(
        self, venue_id: int, assignment_id: int, current_user: User
    ) -> VenueStaff:
        await self._manageable_venue(venue_id, current_user)
        assignment = await self._active_assignment(venue_id, assignment_id)
        assignment.revoked_at = datetime.now(UTC)
        return await self.repository.update(assignment)

    async def _active_assignment(self, venue_id: int, assignment_id: int) -> VenueStaff:
        assignment = await self.repository.get_active_by_id(venue_id, assignment_id)
        if assignment is None:
            raise HTTPException(
                status_code=404, detail="Venue staff assignment not found"
            )
        return assignment
