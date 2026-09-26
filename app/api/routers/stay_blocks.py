from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.stay_block import StayBlockCreate, StayBlockPage, StayBlockRead
from app.services.stay_block_service import StayBlockService

router = APIRouter(tags=["Owner stay blocks"])


@router.get("/owner/properties/{property_id}/stay-blocks", response_model=StayBlockPage)
async def list_blocks(
    property_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await StayBlockService(db).list(property_id, user, offset, limit)


@router.post(
    "/owner/properties/{property_id}/stay-blocks",
    response_model=StayBlockRead,
    status_code=201,
)
async def create_block(
    property_id: int,
    data: StayBlockCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await StayBlockService(db).create(property_id, data, user)


@router.delete(
    "/owner/properties/{property_id}/stay-blocks/{block_id}", status_code=204
)
async def remove_block(
    property_id: int,
    block_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    await StayBlockService(db).remove(property_id, block_id, user)
    return Response(status_code=204)
