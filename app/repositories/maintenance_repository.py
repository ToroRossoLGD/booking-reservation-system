from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.maintenance import MaintenanceActivity, MaintenanceWorkOrder


class MaintenanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, work_order: MaintenanceWorkOrder, activity: MaintenanceActivity
    ) -> MaintenanceWorkOrder:
        self.db.add(work_order)
        await self.db.flush()
        activity.work_order_id = work_order.id
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(work_order)
        return work_order

    async def get_for_venue(
        self, work_order_id: int, venue_id: int
    ) -> MaintenanceWorkOrder | None:
        result = await self.db.execute(
            select(MaintenanceWorkOrder).where(
                MaintenanceWorkOrder.id == work_order_id,
                MaintenanceWorkOrder.venue_id == venue_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_venue(
        self,
        venue_id: int,
        status: str | None = None,
        priority: str | None = None,
        assigned_to_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MaintenanceWorkOrder]:
        statement = select(MaintenanceWorkOrder).where(
            MaintenanceWorkOrder.venue_id == venue_id
        )
        if status is not None:
            statement = statement.where(MaintenanceWorkOrder.status == status)
        if priority is not None:
            statement = statement.where(MaintenanceWorkOrder.priority == priority)
        if assigned_to_id is not None:
            statement = statement.where(
                MaintenanceWorkOrder.assigned_to_id == assigned_to_id
            )
        result = await self.db.execute(
            statement.order_by(
                MaintenanceWorkOrder.created_at.desc(), MaintenanceWorkOrder.id.desc()
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def save(
        self, work_order: MaintenanceWorkOrder, activity: MaintenanceActivity
    ) -> MaintenanceWorkOrder:
        activity.work_order_id = work_order.id
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(work_order)
        return work_order

    async def add_activity(self, activity: MaintenanceActivity) -> MaintenanceActivity:
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)
        return activity

    async def list_activity(self, work_order_id: int) -> list[MaintenanceActivity]:
        result = await self.db.execute(
            select(MaintenanceActivity)
            .where(MaintenanceActivity.work_order_id == work_order_id)
            .order_by(MaintenanceActivity.created_at, MaintenanceActivity.id)
        )
        return list(result.scalars().all())
