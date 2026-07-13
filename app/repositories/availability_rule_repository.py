from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability_rule import AvailabilityRule


class AvailabilityRuleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        rule: AvailabilityRule,
    ) -> AvailabilityRule:
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    async def get_by_id(
        self,
        rule_id: int,
    ) -> AvailabilityRule | None:
        result = await self.db.execute(
            select(AvailabilityRule).where(AvailabilityRule.id == rule_id)
        )

        return result.scalar_one_or_none()

    async def get_for_resource(
        self,
        resource_id: int,
    ) -> list[AvailabilityRule]:
        result = await self.db.execute(
            select(AvailabilityRule)
            .where(AvailabilityRule.resource_id == resource_id)
            .order_by(
                AvailabilityRule.weekday,
                AvailabilityRule.start_time,
            )
        )

        return list(result.scalars().all())

    async def get_for_resource_and_weekday(
        self,
        resource_id: int,
        weekday: int,
    ) -> list[AvailabilityRule]:
        result = await self.db.execute(
            select(AvailabilityRule)
            .where(
                AvailabilityRule.resource_id == resource_id,
                AvailabilityRule.weekday == weekday,
            )
            .order_by(AvailabilityRule.start_time)
        )

        return list(result.scalars().all())

    async def has_overlapping_rule(
        self,
        resource_id: int,
        weekday: int,
        start_time: time,
        end_time: time,
    ) -> bool:
        result = await self.db.execute(
            select(AvailabilityRule.id).where(
                AvailabilityRule.resource_id == resource_id,
                AvailabilityRule.weekday == weekday,
                AvailabilityRule.start_time < end_time,
                AvailabilityRule.end_time > start_time,
            )
        )

        return result.scalar_one_or_none() is not None

    async def delete(
        self,
        rule: AvailabilityRule,
    ) -> None:
        await self.db.delete(rule)
        await self.db.commit()
