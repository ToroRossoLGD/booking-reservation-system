import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class PasswordResetService:
    GENERIC_REQUEST_MESSAGE = (
        "If an account exists for that email, password reset instructions "
        "will be sent if delivery is available."
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
        if settings.DEMO_MODE:
            raise HTTPException(403, "Password recovery is disabled in demo mode")
        if settings.SMTP_MODE == "disabled":
            raise HTTPException(503, "Password recovery is temporarily unavailable")
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
            self._deliver_reset,
            user.email,
            "Bookica — promena lozinke",
            "Za promenu lozinke otvorite link:\n"
            f"{settings.FRONTEND_URL.rstrip('/')}/reset-password"
            f"#token={quote(raw_token, safe='')}\n\n"
            f"Link važi {settings.PASSWORD_RESET_EXPIRE_MINUTES} minuta "
            "i može se koristiti jednom.\n"
            "Ako niste tražili promenu, zanemarite poruku.",
        )
        return {"message": self.GENERIC_REQUEST_MESSAGE}

    def _deliver_reset(self, recipient, subject, body):
        try:
            self.email_service.send_email(recipient, subject, body)
        except Exception:
            # Never log token, recipient, message body or SMTP exception details.
            logger.warning("Password reset email delivery failed")

    async def confirm_reset(self, token: str, new_password: str) -> dict[str, str]:
        if settings.DEMO_MODE:
            raise HTTPException(403, "Password recovery is disabled in demo mode")
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
