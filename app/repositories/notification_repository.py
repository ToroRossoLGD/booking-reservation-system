from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        notification: Notification,
    ) -> Notification:
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def create_once(
        self,
        notification: Notification,
    ) -> Notification | None:
        statement = (
            insert(Notification)
            .values(
                user_id=notification.user_id,
                title=notification.title,
                message=notification.message,
                deduplication_key=notification.deduplication_key,
            )
            .on_conflict_do_nothing(index_elements=["deduplication_key"])
            .returning(Notification)
        )
        result = await self.db.execute(statement)
        created_notification = result.scalar_one_or_none()
        await self.db.commit()
        return created_notification

    async def get_by_user_id(
        self,
        user_id: int,
        limit: int,
        offset: int,
        is_read: bool | None = None,
    ) -> list[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)

        if is_read is not None:
            query = query.where(Notification.is_read.is_(is_read))

        query = (
            query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        )

        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def count_by_user_id(
        self,
        user_id: int,
        is_read: bool | None = None,
    ) -> int:
        query = select(func.count(Notification.id)).where(
            Notification.user_id == user_id
        )

        if is_read is not None:
            query = query.where(Notification.is_read.is_(is_read))

        result = await self.db.execute(query)

        return result.scalar_one()
