from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.maintenance import (
    MaintenanceActivity,
    MaintenanceWorkOrder,
    WorkOrderActivityType,
    WorkOrderStatus,
)
from app.models.user import User
from app.repositories.maintenance_repository import MaintenanceRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.user_repository import UserRepository
from app.repositories.venue_repository import VenueRepository
from app.repositories.venue_staff_repository import VenueStaffRepository
from app.schemas.maintenance import (
    WorkOrderAssignment,
    WorkOrderComment,
    WorkOrderCreate,
    WorkOrderTransition,
    WorkOrderUpdate,
)


class MaintenanceService:
    ACCESS_ROLES = {"manager", "check_in_agent"}
    MANAGER_ROLES = {"manager"}
    TRANSITIONS = {
        "open": {"in_progress", "on_hold", "cancelled"},
        "in_progress": {"on_hold", "resolved", "cancelled"},
        "on_hold": {"in_progress", "cancelled"},
        "resolved": {"open"},
        "cancelled": {"open"},
    }

    def __init__(self, db: AsyncSession):
        self.repository = MaintenanceRepository(db)
        self.venue_repository = VenueRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.user_repository = UserRepository(db)
        self.staff_repository = VenueStaffRepository(db)

    async def _authorize(self, venue_id: int, user: User, manage: bool = False):
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if user.role == "admin" or venue.owner_id == user.id:
            return venue
        roles = self.MANAGER_ROLES if manage else self.ACCESS_ROLES
        if await self.staff_repository.has_role(venue_id, user.id, roles):
            return venue
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this venue's maintenance work orders",
        )

    async def _get(self, venue_id: int, work_order_id: int):
        item = await self.repository.get_for_venue(work_order_id, venue_id)
        if item is None:
            raise HTTPException(
                status_code=404, detail="Maintenance work order not found"
            )
        return item

    def _activity(
        self,
        actor_id: int,
        activity_type: WorkOrderActivityType,
        message: str | None = None,
        details: dict | None = None,
    ):
        return MaintenanceActivity(
            actor_id=actor_id,
            activity_type=activity_type.value,
            message=message,
            details=details or {},
            created_at=datetime.now(UTC),
        )

    async def create(self, venue_id: int, data: WorkOrderCreate, user: User):
        await self._authorize(venue_id, user)
        if data.resource_id is not None:
            resource = await self.resource_repository.get_by_id(data.resource_id)
            if resource is None or resource.venue_id != venue_id:
                raise HTTPException(
                    status_code=400, detail="Resource does not belong to this venue"
                )
        now = datetime.now(UTC)
        item = MaintenanceWorkOrder(
            venue_id=venue_id,
            resource_id=data.resource_id,
            title=data.title,
            description=data.description,
            priority=data.priority,
            status=WorkOrderStatus.OPEN.value,
            reported_by_id=user.id,
            due_at=data.due_at,
            created_at=now,
            updated_at=now,
        )
        return await self.repository.create(
            item,
            self._activity(
                user.id,
                WorkOrderActivityType.CREATED,
                details={"priority": data.priority, "resource_id": data.resource_id},
            ),
        )

    async def list(self, venue_id: int, user: User, **filters):
        await self._authorize(venue_id, user)
        return await self.repository.list_for_venue(venue_id, **filters)

    async def get(self, venue_id: int, work_order_id: int, user: User):
        await self._authorize(venue_id, user)
        return await self._get(venue_id, work_order_id)

    async def update(
        self, venue_id: int, work_order_id: int, data: WorkOrderUpdate, user: User
    ):
        await self._authorize(venue_id, user, manage=True)
        item = await self._get(venue_id, work_order_id)
        changes = data.model_dump(exclude_unset=True)
        before = {key: getattr(item, key) for key in changes}
        for key, value in changes.items():
            setattr(item, key, value)
        item.updated_at = datetime.now(UTC)
        return await self.repository.save(
            item,
            self._activity(
                user.id,
                WorkOrderActivityType.UPDATED,
                details={"before": before, "after": changes},
            ),
        )

    async def assign(
        self, venue_id: int, work_order_id: int, data: WorkOrderAssignment, user: User
    ):
        venue = await self._authorize(venue_id, user, manage=True)
        item = await self._get(venue_id, work_order_id)
        assignee_id = data.assigned_to_id
        if assignee_id is not None:
            assignee = await self.user_repository.get_by_id(assignee_id)
            eligible = assignee is not None and (
                assignee.role == "admin"
                or assignee.id == venue.owner_id
                or await self.staff_repository.has_role(
                    venue_id, assignee.id, self.ACCESS_ROLES
                )
            )
            if not eligible:
                raise HTTPException(
                    status_code=400, detail="Assignee must be active venue staff"
                )
        previous = item.assigned_to_id
        item.assigned_to_id = assignee_id
        item.updated_at = datetime.now(UTC)
        return await self.repository.save(
            item,
            self._activity(
                user.id,
                WorkOrderActivityType.ASSIGNED,
                details={
                    "previous_assignee_id": previous,
                    "assigned_to_id": assignee_id,
                },
            ),
        )

    async def transition(
        self, venue_id: int, work_order_id: int, data: WorkOrderTransition, user: User
    ):
        await self._authorize(venue_id, user, manage=True)
        item = await self._get(venue_id, work_order_id)
        if data.status == item.status:
            raise HTTPException(
                status_code=409, detail="Work order already has this status"
            )
        allowed_transitions = self.TRANSITIONS.get(item.status)
        if allowed_transitions is None:
            raise HTTPException(
                status_code=409,
                detail=f"Work order has unsupported status: {item.status}",
            )
        if data.status not in allowed_transitions:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot transition work order from {item.status} to {data.status}"
                ),
            )
        previous = item.status
        now = datetime.now(UTC)
        item.status = data.status
        item.resolved_at = (
            now if data.status == WorkOrderStatus.RESOLVED.value else None
        )
        item.updated_at = now
        return await self.repository.save(
            item,
            self._activity(
                user.id,
                WorkOrderActivityType.STATUS_CHANGED,
                message=data.note,
                details={"previous_status": previous, "status": data.status},
            ),
        )

    async def comment(
        self, venue_id: int, work_order_id: int, data: WorkOrderComment, user: User
    ):
        await self._authorize(venue_id, user)
        await self._get(venue_id, work_order_id)
        activity = self._activity(
            user.id,
            WorkOrderActivityType.COMMENTED,
            message=data.message,
        )
        activity.work_order_id = work_order_id
        return await self.repository.add_activity(activity)

    async def activity(self, venue_id: int, work_order_id: int, user: User):
        await self._authorize(venue_id, user)
        await self._get(venue_id, work_order_id)
        return await self.repository.list_activity(work_order_id)
