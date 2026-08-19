from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository
from app.services.email_service import EmailService


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.notification_repository = NotificationRepository(db)
        self.email_service = EmailService()

    async def create_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        user_email: str | None = None,
        background_tasks: BackgroundTasks | None = None,
        deduplication_key: str | None = None,
    ) -> Notification | None:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            deduplication_key=deduplication_key,
        )

        if deduplication_key is None:
            created_notification = await self.notification_repository.create(
                notification
            )
        else:
            created_notification = await self.notification_repository.create_once(
                notification
            )

        if created_notification is None:
            return None

        if user_email:
            if background_tasks:
                background_tasks.add_task(
                    self.email_service.send_email,
                    user_email,
                    title,
                    message,
                )
            else:
                self.email_service.send_email(
                    to_email=user_email,
                    subject=title,
                    body=message,
                )

        return created_notification

    async def get_my_notifications(
        self,
        user_id: int,
        limit: int,
        offset: int,
        is_read: bool | None = None,
    ) -> dict:
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="offset must be greater than or equal to 0",
            )

        items = await self.notification_repository.get_by_user_id(
            user_id=user_id,
            limit=limit,
            offset=offset,
            is_read=is_read,
        )

        total = await self.notification_repository.count_by_user_id(
            user_id=user_id,
            is_read=is_read,
        )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
        }

    async def mark_notification_as_read(
        self,
        notification_id: int,
        user_id: int,
    ) -> Notification:
        notification = await self.notification_repository.get_by_id_for_user(
            notification_id=notification_id,
            user_id=user_id,
        )

        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )

        if notification.is_read:
            return notification

        return await self.notification_repository.mark_as_read(notification)

    async def mark_all_notifications_as_read(
        self,
        user_id: int,
    ) -> None:
        await self.notification_repository.mark_all_as_read(user_id)

    async def get_unread_count(
        self,
        user_id: int,
    ) -> int:
        return await self.notification_repository.count_unread(user_id)
