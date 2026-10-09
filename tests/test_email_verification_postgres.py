import asyncio
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.services.email_verification_service import EmailVerificationService


@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI uses PostgreSQL locks"
)
@pytest.mark.asyncio
async def test_concurrent_resend_and_confirmation_are_single_use(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_MODE", "plain")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = None
    try:
        async with sessions() as db:
            user = User(
                email=f"verify-{uuid4().hex}@example.com",
                hashed_password="unused",
                role="customer",
            )
            db.add(user)
            await db.commit()
            user_id = user.id

        async def issue():
            async with sessions() as db:
                user = await db.get(User, user_id)
                tasks = BackgroundTasks()
                await EmailVerificationService(db).request(user, tasks)
                return tasks.tasks

        results = await asyncio.wait_for(asyncio.gather(issue(), issue()), 20)
        messages = [task for tasks in results for task in tasks]
        assert len(messages) == 1
        old = parse_qs(urlsplit(messages[0].args[1]).fragment)["token"][0]
        async with sessions() as db:
            await db.execute(
                update(EmailVerificationToken)
                .where(EmailVerificationToken.user_id == user_id)
                .values(created_at=datetime.now(UTC) - timedelta(minutes=2))
            )
            await db.commit()
        resend = await issue()
        new = parse_qs(urlsplit(resend[0].args[1]).fragment)["token"][0]

        async def confirm(raw):
            async with sessions() as db:
                try:
                    await EmailVerificationService(db).confirm(raw)
                    return 200
                except HTTPException as exc:
                    return exc.status_code

        assert await confirm(old) == 409
        results = await asyncio.wait_for(asyncio.gather(confirm(new), confirm(new)), 20)
        assert sorted(results) == [200, 409]
        async with sessions() as db:
            user = await db.get(User, user_id)
            assert user.email_verified
            assert (
                await db.scalar(
                    select(EmailVerificationToken.id).where(
                        EmailVerificationToken.user_id == user_id,
                        EmailVerificationToken.consumed_at.is_(None),
                    )
                )
                is None
            )
        assert await issue() == []
    finally:
        if user_id is not None:
            async with sessions() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
        await engine.dispose()
