from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationListRead,
)
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.get(
    "/my",
    response_model=NotificationListRead,
)
async def get_my_notifications(
    limit: int = 20,
    offset: int = 0,
    is_read: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)

    return await service.get_my_notifications(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        is_read=is_read,
    )
