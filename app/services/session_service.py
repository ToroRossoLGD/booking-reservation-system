from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.user import User


class SessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def revoke_all(self, current_user: User) -> None:
        expected_version = current_user.token_version
        user = await self.db.scalar(
            select(User)
            .where(User.id == current_user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        # A previously authenticated request waiting on the lock must not revoke
        # sessions issued after another revocation/password reset has committed.
        if user is None or user.token_version != expected_version:
            await self.db.rollback()
            raise HTTPException(401, "Session is no longer valid")
        try:
            user.token_version += 1
            await self.db.execute(
                update(APIKey)
                .where(APIKey.user_id == user.id, APIKey.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
