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
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
        )

        created_notification = await self.notification_repository.create(
            notification
        )

        if user_email:
            self.email_service.send_email(
                to_email=user_email,
                subject=title,
                body=message,
            )

        return created_notification

    async def get_my_notifications(
        self,
        user_id: int,
    ) -> list[Notification]:
        return await self.notification_repository.get_by_user_id(user_id)