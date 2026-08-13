from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentRead
from app.services.payment_service import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


@router.get(
    "/reservations/{reservation_id}",
    response_model=PaymentRead,
)
async def get_reservation_payment(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)

    return await service.get_reservation_payment(
        reservation_id=reservation_id,
        current_user=current_user,
    )


@router.post(
    "/reservations/{reservation_id}/pay",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
async def pay_for_reservation(
    reservation_id: int,
    data: PaymentCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)

    return await service.pay_for_reservation(
        reservation_id=reservation_id,
        data=data,
        current_user=current_user,
        background_tasks=background_tasks,
    )
