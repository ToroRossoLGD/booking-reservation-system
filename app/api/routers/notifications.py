from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    DismissedNotificationCount,
    NotificationListRead,
    NotificationRead,
    UnreadNotificationCount,
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


@router.get("/unread-count", response_model=UnreadNotificationCount)
async def get_unread_notification_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    unread_count = await NotificationService(db).get_unread_count(current_user.id)
    return UnreadNotificationCount(unread_count=unread_count)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await NotificationService(db).mark_notification_as_read(
        notification_id=notification_id,
        user_id=current_user.id,
    )


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await NotificationService(db).mark_all_notifications_as_read(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/read", response_model=DismissedNotificationCount)
async def dismiss_read_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dismissed_count = await NotificationService(db).dismiss_read_notifications(
        current_user.id
    )
    return DismissedNotificationCount(dismissed_count=dismissed_count)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await NotificationService(db).dismiss_notification(
        notification_id=notification_id,
        user_id=current_user.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
