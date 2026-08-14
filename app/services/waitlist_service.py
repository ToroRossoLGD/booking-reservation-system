from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.waitlist_entry import WaitlistEntry
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.waitlist_repository import WaitlistRepository
from app.schemas.waitlist import WaitlistEntryCreate
from app.services.notification_service import NotificationService


class WaitlistService:
    def __init__(self, db: AsyncSession):
        self.waitlist_repository = WaitlistRepository(db)
        self.reservation_repository = ReservationRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.notification_service = NotificationService(db)

    async def join_waitlist(
        self, data: WaitlistEntryCreate, current_user: User
    ) -> WaitlistEntry:
        if data.start_time.tzinfo is None or data.end_time.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Waitlist times must include a timezone",
            )
        if data.start_time >= data.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )
        if data.start_time <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Waitlist time must be in the future",
            )

        if await self.resource_repository.get_by_id(data.resource_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        conflict = await self.reservation_repository.get_conflicting_reservation(
            resource_id=data.resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
        )
        if conflict is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This time is available and does not require a waitlist",
            )
        if conflict.user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot join the waitlist for your own reservation",
            )

        existing = await self.waitlist_repository.get_waiting_entry(
            user_id=current_user.id,
            resource_id=data.resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You are already waiting for this time slot",
            )

        created_entry = await self.waitlist_repository.create(
            WaitlistEntry(
                user_id=current_user.id,
                resource_id=data.resource_id,
                start_time=data.start_time,
                end_time=data.end_time,
            )
        )

        if created_entry is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You are already waiting for this time slot",
            )

        return created_entry

    async def get_my_waitlist(self, current_user: User) -> list[WaitlistEntry]:
        return await self.waitlist_repository.get_for_user(current_user.id)

    async def leave_waitlist(self, entry_id: int, current_user: User) -> None:
        entry = await self.waitlist_repository.get_by_id_for_user(
            entry_id=entry_id, user_id=current_user.id
        )
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Waitlist entry not found",
            )
        await self.waitlist_repository.delete(entry)

    async def notify_next_for_slot(
        self, resource_id: int, start_time: datetime, end_time: datetime
    ) -> WaitlistEntry | None:
        entry = await self.waitlist_repository.get_next_waiting_for_slot(
            resource_id=resource_id,
            start_time=start_time,
            end_time=end_time,
        )
        if entry is None:
            return None

        entry = await self.waitlist_repository.mark_notified(entry)
        await self.notification_service.create_notification(
            user_id=entry.user_id,
            title="A reservation time is available",
            message=(
                f"The time you requested for resource #{resource_id}, starting at "
                f"{start_time.isoformat()}, is now available."
            ),
        )
        return entry
