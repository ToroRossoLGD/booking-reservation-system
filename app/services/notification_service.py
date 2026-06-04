from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.notification_repository = NotificationRepository(db)

    async def create_notification(
        self,
        user_id: int,
        title: str,
        message: str,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
        )

        return await self.notification_repository.create(notification)

    async def get_my_notifications(
        self,
        user_id: int,
    ) -> list[Notification]:
        return await self.notification_repository.get_by_user_id(user_id)