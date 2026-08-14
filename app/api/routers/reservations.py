from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.reservation import (
    AvailabilityRead,
    AvailableSlotRead,
    RecurringReservationCreate,
    RecurringReservationRead,
    ReservationCancellationRead,
    ReservationCreate,
    ReservationListRead,
    ReservationRead,
    ReservationReschedule,
)
from app.services.reservation_service import ReservationService
from app.tasks.reservation_tasks import expire_pending_reservations_task

router = APIRouter(
    prefix="/reservations",
    tags=["Reservations"],
)


@router.post("", response_model=ReservationRead, status_code=201)
async def create_reservation(
    data: ReservationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)

    return await service.create_reservation(
        data=data,
        current_user=current_user,
        background_tasks=background_tasks,
    )


@router.post(
    "/recurring",
    response_model=RecurringReservationRead,
    status_code=201,
)
async def create_recurring_reservations(
    data: RecurringReservationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)
    return await service.create_recurring_reservations(
        data=data,
        current_user=current_user,
        background_tasks=background_tasks,
    )


@router.get(
    "/series/{recurrence_series_id}",
    response_model=RecurringReservationRead,
)
async def get_recurring_reservations(
    recurrence_series_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)
    return await service.get_recurring_reservations(
        recurrence_series_id=recurrence_series_id,
        current_user=current_user,
    )


@router.get("/my", response_model=ReservationListRead)
async def get_my_reservations(
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)

    return await service.get_my_reservations(
        current_user=current_user,
        limit=limit,
        offset=offset,
        status_filter=status,
    )


@router.patch(
    "/{reservation_id}/cancel",
    response_model=ReservationCancellationRead,
)
async def cancel_reservation(
    reservation_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)

    return await service.cancel_reservation(
        reservation_id=reservation_id,
        current_user=current_user,
        background_tasks=background_tasks,
    )


@router.get(
    "/resources/{resource_id}/availability",
    response_model=AvailabilityRead,
)
async def check_resource_availability(
    resource_id: int,
    start_time: datetime,
    end_time: datetime,
    db: AsyncSession = Depends(get_db),
):
    service = ReservationService(db)

    return await service.check_availability(
        resource_id=resource_id,
        start_time=start_time,
        end_time=end_time,
    )


@router.get(
    "/resources/{resource_id}/available-slots",
    response_model=list[AvailableSlotRead],
)
async def get_available_slots(
    resource_id: int,
    selected_date: date,
    slot_minutes: int = Query(default=60, gt=0, le=1440),
    db: AsyncSession = Depends(get_db),
):
    service = ReservationService(db)

    return await service.get_available_slots(
        resource_id=resource_id,
        selected_date=selected_date,
        slot_minutes=slot_minutes,
    )


@router.get(
    "/{reservation_id}",
    response_model=ReservationRead,
)
async def get_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)

    return await service.get_reservation(
        reservation_id=reservation_id,
        current_user=current_user,
    )


@router.patch(
    "/{reservation_id}/reschedule",
    response_model=ReservationRead,
)
async def reschedule_reservation(
    reservation_id: int,
    data: ReservationReschedule,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationService(db)

    return await service.reschedule_reservation(
        reservation_id=reservation_id,
        data=data,
        current_user=current_user,
    )


@router.patch(
    "/{reservation_id}/confirm",
    response_model=ReservationRead,
)
async def confirm_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = ReservationService(db)

    return await service.confirm_reservation(
        reservation_id=reservation_id,
        current_user=current_user,
    )


@router.patch(
    "/{reservation_id}/complete",
    response_model=ReservationRead,
)
async def complete_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = ReservationService(db)

    return await service.complete_reservation(
        reservation_id=reservation_id,
        current_user=current_user,
    )


@router.post("/expire-pending")
async def expire_pending_reservations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    service = ReservationService(db)

    return await service.expire_pending_reservations()


@router.post("/expire-pending/background")
async def expire_pending_reservations_background(
    current_user: User = Depends(require_roles("admin")),
):
    task = expire_pending_reservations_task.delay()

    return {
        "task_id": task.id,
        "status": "queued",
    }
