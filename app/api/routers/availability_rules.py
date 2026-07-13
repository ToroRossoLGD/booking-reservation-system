from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.availability_rule import (
    AvailabilityRuleCreate,
    AvailabilityRuleRead,
)
from app.services.availability_rule_service import (
    AvailabilityRuleService,
)

router = APIRouter(
    prefix="/resources",
    tags=["Availability Rules"],
)


@router.post(
    "/{resource_id}/availability-rules",
    response_model=AvailabilityRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability_rule(
    resource_id: int,
    data: AvailabilityRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AvailabilityRuleService(db)

    return await service.create_rule(
        resource_id=resource_id,
        data=data,
        current_user=current_user,
    )


@router.get(
    "/{resource_id}/availability-rules",
    response_model=list[AvailabilityRuleRead],
)
async def get_availability_rules(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = AvailabilityRuleService(db)

    return await service.get_resource_rules(resource_id=resource_id)


@router.delete(
    "/{resource_id}/availability-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_availability_rule(
    resource_id: int,
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AvailabilityRuleService(db)

    await service.delete_rule(
        resource_id=resource_id,
        rule_id=rule_id,
        current_user=current_user,
    )
