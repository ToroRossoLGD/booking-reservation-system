from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus


class WaitlistRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_waiting_entry(
        self,
        user_id: int,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> WaitlistEntry | None:
        result = await self.db.execute(
            select(WaitlistEntry).where(
                WaitlistEntry.user_id == user_id,
                WaitlistEntry.resource_id == resource_id,
                WaitlistEntry.start_time == start_time,
                WaitlistEntry.end_time == end_time,
                WaitlistEntry.status == WaitlistStatus.WAITING.value,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, entry: WaitlistEntry) -> WaitlistEntry | None:
        self.db.add(entry)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            return None
        await self.db.refresh(entry)
        return entry

    async def get_for_user(self, user_id: int) -> list[WaitlistEntry]:
        result = await self.db.execute(
            select(WaitlistEntry)
            .where(WaitlistEntry.user_id == user_id)
            .order_by(WaitlistEntry.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, entry_id: int, user_id: int
    ) -> WaitlistEntry | None:
        result = await self.db.execute(
            select(WaitlistEntry).where(
                WaitlistEntry.id == entry_id,
                WaitlistEntry.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, entry: WaitlistEntry) -> None:
        await self.db.delete(entry)
        await self.db.commit()

    async def get_next_waiting_for_slot(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> WaitlistEntry | None:
        result = await self.db.execute(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.resource_id == resource_id,
                WaitlistEntry.start_time >= start_time,
                WaitlistEntry.end_time <= end_time,
                WaitlistEntry.status == WaitlistStatus.WAITING.value,
            )
            .order_by(WaitlistEntry.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_notified(self, entry: WaitlistEntry) -> WaitlistEntry:
        entry.status = WaitlistStatus.NOTIFIED.value
        entry.notified_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry
