from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.availability_exception import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionRead,
)
from app.services.availability_exception_service import (
    AvailabilityExceptionService,
)

router = APIRouter(
    prefix="/resources",
    tags=["Availability Exceptions"],
)


@router.post(
    "/{resource_id}/availability-exceptions",
    response_model=AvailabilityExceptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability_exception(
    resource_id: int,
    data: AvailabilityExceptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AvailabilityExceptionService(db)

    return await service.create_exception(
        resource_id=resource_id,
        data=data,
        current_user=current_user,
    )


@router.get(
    "/{resource_id}/availability-exceptions",
    response_model=list[AvailabilityExceptionRead],
)
async def get_availability_exceptions(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = AvailabilityExceptionService(db)

    return await service.get_resource_exceptions(resource_id=resource_id)


@router.delete(
    "/{resource_id}/availability-exceptions/{exception_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_availability_exception(
    resource_id: int,
    exception_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AvailabilityExceptionService(db)

    await service.delete_exception(
        resource_id=resource_id,
        exception_id=exception_id,
        current_user=current_user,
    )
