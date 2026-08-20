import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService


class PasswordResetService:
    GENERIC_REQUEST_MESSAGE = (
        "If an account exists for that email, a password reset message has been sent."
    )

    def __init__(self, db: AsyncSession):
        self.repository = PasswordResetRepository(db)
        self.user_repository = UserRepository(db)
        self.email_service = EmailService()

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def request_reset(
        self, email: str, background_tasks: BackgroundTasks
    ) -> dict[str, str]:
        user = await self.user_repository.get_by_email(email.lower())
        if user is None:
            return {"message": self.GENERIC_REQUEST_MESSAGE}

        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=self._hash_token(raw_token),
            created_at=now,
            expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        )
        reset_token = await self.repository.replace_active_token(reset_token, now)
        background_tasks.add_task(
            self.email_service.send_email,
            user.email,
            "Reset your password",
            f"Use this token to reset your password: {raw_token}\n"
            f"It expires at {reset_token.expires_at.isoformat()}.",
        )
        return {"message": self.GENERIC_REQUEST_MESSAGE}

    async def confirm_reset(self, token: str, new_password: str) -> dict[str, str]:
        token_hash = self._hash_token(token)
        reset_token = await self.repository.get_by_hash(token_hash)
        if reset_token is None:
            raise HTTPException(status_code=400, detail="Invalid password reset token")
        if reset_token.consumed_at is not None:
            raise HTTPException(
                status_code=409, detail="Password reset token has already been used"
            )
        now = datetime.now(UTC)
        if reset_token.expires_at <= now:
            raise HTTPException(
                status_code=410, detail="Password reset token has expired"
            )
        consumed = await self.repository.consume_and_change_password(
            token_hash=token_hash,
            now=now,
            hashed_password=hash_password(new_password),
        )
        if not consumed:
            raise HTTPException(
                status_code=409, detail="Password reset token is no longer valid"
            )
        return {"message": "Password has been reset successfully."}
