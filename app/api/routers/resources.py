from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.resource import ResourceCreate, ResourceRead
from app.services.resource_service import ResourceService


router = APIRouter(
    tags=["Resources"],
)


@router.post(
    "/venues/{venue_id}/resources",
    response_model=ResourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource(
    venue_id: int,
    data: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = ResourceService(db)
    return await service.create_resource(
        venue_id=venue_id,
        data=data,
        current_user=current_user,
    )


@router.get(
    "/venues/{venue_id}/resources",
    response_model=list[ResourceRead],
)
async def get_resources_by_venue(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = ResourceService(db)
    return await service.get_resources_by_venue(venue_id)


@router.get(
    "/resources/{resource_id}",
    response_model=ResourceRead,
)
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = ResourceService(db)
    return await service.get_resource_by_id(resource_id)


@router.delete(
    "/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    service = ResourceService(db)
    await service.delete_resource(
        resource_id=resource_id,
        current_user=current_user,
    )