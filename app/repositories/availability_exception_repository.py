from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability_exception import AvailabilityException


class AvailabilityExceptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        exception: AvailabilityException,
    ) -> AvailabilityException:
        self.db.add(exception)
        await self.db.commit()
        await self.db.refresh(exception)

        return exception

    async def get_by_id(
        self,
        exception_id: int,
    ) -> AvailabilityException | None:
        result = await self.db.execute(
            select(AvailabilityException).where(
                AvailabilityException.id == exception_id
            )
        )

        return result.scalar_one_or_none()

    async def get_for_resource(
        self,
        resource_id: int,
    ) -> list[AvailabilityException]:
        result = await self.db.execute(
            select(AvailabilityException)
            .where(AvailabilityException.resource_id == resource_id)
            .order_by(AvailabilityException.start_time)
        )

        return list(result.scalars().all())

    async def has_overlapping_exception(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        result = await self.db.execute(
            select(AvailabilityException.id).where(
                AvailabilityException.resource_id == resource_id,
                AvailabilityException.start_time < end_time,
                AvailabilityException.end_time > start_time,
            )
        )

        return result.scalar_one_or_none() is not None

    async def get_overlapping_exceptions(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[AvailabilityException]:
        result = await self.db.execute(
            select(AvailabilityException)
            .where(
                AvailabilityException.resource_id == resource_id,
                AvailabilityException.start_time < end_time,
                AvailabilityException.end_time > start_time,
            )
            .order_by(AvailabilityException.start_time)
        )

        return list(result.scalars().all())

    async def delete(
        self,
        exception: AvailabilityException,
    ) -> None:
        await self.db.delete(exception)
        await self.db.commit()
