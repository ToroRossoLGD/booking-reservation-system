from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.maintenance import (
    Priority,
    Status,
    WorkOrderActivityRead,
    WorkOrderAssignment,
    WorkOrderComment,
    WorkOrderCreate,
    WorkOrderRead,
    WorkOrderTransition,
    WorkOrderUpdate,
)
from app.services.maintenance_service import MaintenanceService

router = APIRouter(
    prefix="/venues/{venue_id}/maintenance/work-orders",
    tags=["Maintenance Work Orders"],
)


@router.post("", response_model=WorkOrderRead, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    venue_id: int,
    data: WorkOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MaintenanceService(db).create(venue_id, data, current_user)


@router.get("", response_model=list[WorkOrderRead])
async def list_work_orders(
    venue_id: int,
    status_filter: Status | None = Query(default=None, alias="status"),
    priority: Priority | None = None,
    assigned_to_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MaintenanceService(db).list(
        venue_id,
        current_user,
        status=status_filter,
        priority=priority,
        assigned_to_id=assigned_to_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{work_order_id}", response_model=WorkOrderRead)
async def get_work_order(
    venue_id: int,
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MaintenanceService(db).get(venue_id, work_order_id, current_user)


@router.patch("/{work_order_id}", response_model=WorkOrderRead)
async def update_work_order(
    venue_id: int,
    work_order_id: int,
    data: WorkOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MaintenanceService(db).update(
        venue_id, work_order_id, data, current_user
    )


@router.post("/{work_order_id}/assignment", response_model=WorkOrderRead)
async def assign_work_order(
    venue_id: int,
    work_order_id: int,
    data: WorkOrderAssignment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MaintenanceService(db).assign(
        venue_id, work_order_id, data, current_user
    )


@router.post("/{work_order_id}/transition", response_model=WorkOrderRead)
async def transition_work_order(
    venue_id: int,
    work_order_id: int,
    data: WorkOrderTransition,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MaintenanceService(db).transition(
        venue_id, work_order_id, data, current_user
    )


@router.post(
    "/{work_order_id}/comments",
    response_model=WorkOrderActivityRead,
    status_code=status.HTTP_201_CREATED,
)
async def comment_on_work_order(
    venue_id: int,
    work_order_id: int,
    data: WorkOrderComment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MaintenanceService(db).comment(
        venue_id, work_order_id, data, current_user
    )


@router.get("/{work_order_id}/activity", response_model=list[WorkOrderActivityRead])
async def list_work_order_activity(
    venue_id: int,
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MaintenanceService(db).activity(venue_id, work_order_id, current_user)
