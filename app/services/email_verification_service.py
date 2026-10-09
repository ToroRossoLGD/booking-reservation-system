import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.config import settings
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)
MESSAGE = {
    "message": "Verification instructions will be sent if verification is needed."
}


class EmailVerificationService:
    def __init__(self, db):
        self.db = db

    async def request(self, user, background_tasks, automatic=False):
        if settings.DEMO_MODE or settings.SMTP_MODE == "disabled":
            if automatic:
                return MESSAGE
            raise HTTPException(503, "Email verification is currently unavailable")
        # Serialize issuance with confirmation and other account changes.
        current = await self.db.scalar(
            select(User)
            .where(User.id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if current is None:
            raise HTTPException(401, "Account unavailable")
        now = datetime.now(UTC)
        latest = await self.db.scalar(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == current.id)
            .order_by(EmailVerificationToken.created_at.desc())
            .limit(1)
        )
        if current.email_verified or (
            latest and latest.created_at > now - timedelta(seconds=60)
        ):
            await self.db.rollback()
            return MESSAGE
        await self.db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == current.id,
                EmailVerificationToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        raw = secrets.token_urlsafe(32)
        email = current.email
        self.db.add(
            EmailVerificationToken(
                user_id=current.id,
                email=email,
                token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                created_at=now,
                expires_at=now
                + timedelta(minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES),
            )
        )
        await self.db.commit()
        link = (
            f"{settings.FRONTEND_URL.rstrip('/')}/verify-email"
            f"#token={quote(raw, safe='')}"
        )
        background_tasks.add_task(self.deliver, email, link)
        return MESSAGE

    @staticmethod
    def deliver(email, link):
        try:
            EmailService().send_email(
                email,
                "Bookica — potvrda email adrese",
                f"Potvrdite email adresu otvaranjem linka:\n{link}\n\n"
                f"Link važi {settings.EMAIL_VERIFICATION_EXPIRE_MINUTES} minuta. "
                "Ako niste tražili ovu poruku, zanemarite je.",
            )
        except Exception:
            logger.warning("Email verification delivery failed")

    async def confirm(self, raw):
        if settings.DEMO_MODE:
            raise HTTPException(403, "Email verification is disabled in demo mode")
        token = await self.db.scalar(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash
                == hashlib.sha256(raw.encode()).hexdigest()
            )
        )
        if token is None:
            raise HTTPException(400, "Invalid verification link")
        user = await self.db.scalar(
            select(User)
            .where(User.id == token.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            await self.db.rollback()
            raise HTTPException(409, "Verification link is no longer valid")
        await self.db.refresh(token)
        now = datetime.now(UTC)
        if token.consumed_at is not None or token.email != user.email:
            await self.db.rollback()
            raise HTTPException(409, "Verification link is no longer valid")
        if token.expires_at <= now:
            await self.db.rollback()
            raise HTTPException(410, "Verification link has expired")
        user.email_verified_at = now
        await self.db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        await self.db.commit()
        return {"message": "Email address verified."}
