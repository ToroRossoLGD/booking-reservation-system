import asyncio
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.user import User
from app.services.session_service import SessionService


@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI runs PostgreSQL locking tests"
)
@pytest.mark.asyncio
async def test_concurrent_revocations_reject_stale_request():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = None
    try:
        async with sessions() as db:
            user = User(
                email=f"sessions-{uuid4().hex}@example.com",
                hashed_password="test",
                role="customer",
            )
            db.add(user)
            await db.commit()
            user_id = user.id
        async with sessions() as first, sessions() as second:
            users = [await first.get(User, user_id), await second.get(User, user_id)]

            async def revoke(db, user):
                try:
                    await SessionService(db).revoke_all(user)
                    return 204
                except HTTPException as error:
                    return error.status_code

            results = await asyncio.wait_for(
                asyncio.gather(revoke(first, users[0]), revoke(second, users[1])),
                timeout=20,
            )
            assert sorted(results) == [204, 401]
        async with sessions() as db:
            user = await db.get(User, user_id)
            assert user.token_version == 1
    finally:
        if user_id is not None:
            async with sessions() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
        await engine.dispose()
