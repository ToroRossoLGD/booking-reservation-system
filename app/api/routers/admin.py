from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import AdminStatsRead
from app.services.admin_service import AdminService

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get(
    "/stats",
    response_model=AdminStatsRead,
)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    service = AdminService(db)

    return await service.get_stats()
