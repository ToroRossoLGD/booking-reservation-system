from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.core.property_rate_limit import limit_property_account
from app.db.session import get_db
from app.models.user import User
from app.schemas.owner_access import (
    OwnerAccessCreate,
    OwnerAccessDecision,
    OwnerAccessPage,
    OwnerAccessRead,
)
from app.services.owner_access_service import OwnerAccessService

router = APIRouter(tags=["Owner access"])


@router.get("/owner-access/mine", response_model=OwnerAccessPage)
async def mine(
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await OwnerAccessService(db).page(user, offset=offset)


@router.post(
    "/owner-access/requests",
    response_model=OwnerAccessRead,
    status_code=201,
    dependencies=[Depends(limit_property_account)],
)
async def create(
    data: OwnerAccessCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await OwnerAccessService(db).create(data, user)


@router.get("/admin/owner-access", response_model=OwnerAccessPage)
async def queue(
    status: Literal["pending", "approved", "rejected"] | None = "pending",
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    return await OwnerAccessService(db).page(
        user, admin=True, status=status, offset=offset
    )


@router.post(
    "/admin/owner-access/{request_id}/decision", response_model=OwnerAccessRead
)
async def decide(
    request_id: int,
    data: OwnerAccessDecision,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    return await OwnerAccessService(db).decide(request_id, data, user)
