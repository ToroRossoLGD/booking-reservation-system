from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset_token import PasswordResetToken
from app.models.user import User


class PasswordResetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def replace_active_token(
        self, token: PasswordResetToken, now: datetime
    ) -> PasswordResetToken:
        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == token.user_id,
                PasswordResetToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def consume_and_change_password(
        self, token_hash: str, now: datetime, hashed_password: str
    ) -> bool:
        result = await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.consumed_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .values(consumed_at=now)
            .returning(PasswordResetToken.user_id)
        )
        user_id = result.scalar_one_or_none()
        if user_id is None:
            await self.db.rollback()
            return False
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                hashed_password=hashed_password,
                token_version=User.token_version + 1,
            )
        )
        await self.db.commit()
        return True
