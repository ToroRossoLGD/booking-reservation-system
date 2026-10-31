import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, select

from app.core.config import settings
from app.models.notification import Notification
from app.models.property_email_digest import (
    PropertyEmailDigest,
    PropertyEmailDigestItem,
)
from app.models.user import User
from app.services.email_service import EmailDeliveryError, EmailService

PATHS = (
    "/stays",
    "/owner/stays",
    "/rentals",
    "/owner/rentals",
    "/sales",
    "/owner/sales",
)


def available():
    return (
        settings.PROPERTY_EMAIL_DIGEST_ENABLED
        and not settings.DEMO_MODE
        and settings.SMTP_MODE != "disabled"
    )


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def status(db, user):
    row = await db.get(PropertyEmailDigest, user.id)
    return {
        "enabled": bool(row and row.enabled),
        "available": available(),
        "verified": user.email_verified_at is not None,
        "last_status": row.last_status if row else "unconfigured",
        "last_attempt_at": row.last_attempt_at if row else None,
        "last_accepted_at": row.last_accepted_at if row else None,
    }


async def configure(db, user, enabled):
    if settings.DEMO_MODE:
        raise HTTPException(403, "Email digest preferences are disabled in demo mode")
    # Serialize settings without blocking worker FK KEY SHARE locks on the user.
    current_user = await db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if enabled and (not available() or not current_user.email_verified):
        raise HTTPException(
            409, "Email digest requires verified email and enabled delivery"
        )
    row = await db.scalar(
        select(PropertyEmailDigest)
        .where(PropertyEmailDigest.user_id == user.id)
        .with_for_update()
    )
    if row is None:
        row = PropertyEmailDigest(
            user_id=user.id, next_run_at=datetime.now(UTC), enabled=False
        )
        db.add(row)
    if enabled and not row.enabled:
        row.cursor = (
            await db.scalar(
                select(func.max(Notification.id)).where(Notification.user_id == user.id)
            )
            or 0
        )
        row.next_run_at = datetime.now(UTC) + timedelta(hours=1)
        row.attempts = 0
        row.last_status = "pending"
    if row.enabled != enabled:
        row.lease_token = None
        row.lease_until = None
    row.enabled = enabled
    await db.commit()
    return await status(db, current_user)


async def claim(sessions):
    now = datetime.now(UTC)
    async with sessions() as db:
        row = await db.scalar(
            select(PropertyEmailDigest)
            .where(
                PropertyEmailDigest.enabled.is_(True),
                PropertyEmailDigest.next_run_at <= now,
                or_(
                    PropertyEmailDigest.lease_until.is_(None),
                    PropertyEmailDigest.lease_until <= now,
                ),
            )
            .order_by(PropertyEmailDigest.next_run_at, PropertyEmailDigest.user_id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        user = await db.get(User, row.user_id)
        if not user or not user.email_verified:
            row.enabled = False
            row.last_status = "unverified"
            row.lease_token = None
            row.lease_until = None
            await db.commit()
            return {"skip": True}
        ids = list(
            (
                await db.scalars(
                    select(Notification.id)
                    .where(
                        Notification.user_id == row.user_id,
                        Notification.id > row.cursor,
                        Notification.action_path.in_(PATHS),
                        ~select(PropertyEmailDigestItem.notification_id)
                        .where(
                            PropertyEmailDigestItem.user_id == row.user_id,
                            PropertyEmailDigestItem.notification_id == Notification.id,
                        )
                        .exists(),
                    )
                    .order_by(Notification.id)
                    .limit(20)
                )
            ).all()
        )
        row.next_run_at = now + timedelta(hours=1)
        if not ids:
            await db.commit()
            return {"skip": True}
        row.lease_token = str(uuid4())
        row.lease_until = now + timedelta(minutes=10)
        job = {
            "user_id": row.user_id,
            "token": row.lease_token,
            "ids": ids,
            "count": len(ids),
        }
        await db.commit()
        return job


async def send_and_finish(sessions, job):
    # Recheck consent and verified address immediately before SMTP, outside locks.
    async with sessions() as db:
        row = await db.get(PropertyEmailDigest, job["user_id"])
        user = await db.get(User, job["user_id"])
        if (
            not available()
            or not row
            or not row.enabled
            or row.lease_token != job["token"]
            or not row.lease_until
            or utc(row.lease_until) <= datetime.now(UTC)
            or not user
            or not user.email_verified
        ):
            return "discarded"
        recipient = user.email
    failed = False
    try:
        await asyncio.to_thread(
            EmailService().send_email,
            recipient,
            "Bookica: nova obaveštenja o nekretninama",
            f"Imaš {job['count']} novih obaveštenja "
            "o boravcima ili upitima za nekretnine.\n\n"
            f"Proveri aktuelne detalje: {settings.FRONTEND_URL.rstrip('/')}"
            "/account/notifications\n\n"
            "Email sažetak možeš isključiti u podešavanju na istoj stranici. "
            "Poruka ne sadrži privatne detalje rezervacije ili razgovora.",
        )
    except EmailDeliveryError:
        failed = True
    async with sessions() as db:
        row = await db.scalar(
            select(PropertyEmailDigest)
            .where(PropertyEmailDigest.user_id == job["user_id"])
            .with_for_update()
        )
        if not row or row.lease_token != job["token"]:
            return "discarded"
        row.lease_token = None
        row.lease_until = None
        row.last_attempt_at = datetime.now(UTC)
        if failed:
            row.attempts += 1
            row.last_status = "failed"
            row.next_run_at = datetime.now(UTC) + timedelta(minutes=15)
            if row.attempts >= 3:
                row.enabled = False
        else:
            for notification_id in job["ids"]:
                db.add(
                    PropertyEmailDigestItem(
                        user_id=row.user_id, notification_id=notification_id
                    )
                )
            row.attempts = 0
            row.last_status = "accepted"
            row.last_accepted_at = datetime.now(UTC)
        await db.commit()
        return row.last_status


async def run_email_digests(sessions, limit=10):
    counts = {}
    for _ in range(limit):
        if not available():
            break
        job = await claim(sessions)
        if job is None:
            break
        if job.get("skip"):
            continue
        result = await send_and_finish(sessions, job)
        counts[result] = counts.get(result, 0) + 1
    return counts
