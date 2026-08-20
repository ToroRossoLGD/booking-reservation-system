from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.user import User


class APIKeyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_if_below_limit(
        self, api_key: APIKey, now: datetime, maximum: int
    ) -> APIKey | None:
        await self.db.execute(
            select(User.id).where(User.id == api_key.user_id).with_for_update()
        )
        active_count = await self.count_active(api_key.user_id, now)
        if active_count >= maximum:
            await self.db.rollback()
            return None
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key

    async def list_for_user(self, user_id: int) -> list[APIKey]:
        result = await self.db.execute(
            select(APIKey)
            .where(APIKey.user_id == user_id)
            .order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_active(self, user_id: int, now: datetime) -> int:
        result = await self.db.execute(
            select(func.count(APIKey.id)).where(
                APIKey.user_id == user_id,
                APIKey.revoked_at.is_(None),
                (APIKey.expires_at.is_(None) | (APIKey.expires_at > now)),
            )
        )
        return result.scalar_one()

    async def get_for_user(self, api_key_id: int, user_id: int) -> APIKey | None:
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.id == api_key_id,
                APIKey.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        result = await self.db.execute(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def record_use_if_valid(self, key_hash: str, now: datetime) -> int | None:
        result = await self.db.execute(
            update(APIKey)
            .where(
                APIKey.key_hash == key_hash,
                APIKey.revoked_at.is_(None),
                (APIKey.expires_at.is_(None) | (APIKey.expires_at > now)),
            )
            .values(last_used_at=now)
            .returning(APIKey.user_id)
        )
        user_id = result.scalar_one_or_none()
        if user_id is None:
            await self.db.rollback()
        else:
            await self.db.commit()
        return user_id

    async def update(self, api_key: APIKey) -> APIKey:
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key
