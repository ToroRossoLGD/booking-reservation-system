import asyncio
import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.api_key import APIKey
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.password_reset_repository import PasswordResetRepository


@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI runs PostgreSQL locking tests"
)
@pytest.mark.asyncio
async def test_reset_races_revoke_sessions_keys_and_leave_one_active_request():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = None
    now = datetime.now(UTC)
    try:
        async with sessions() as db:
            user = User(
                email=f"recovery-{uuid4().hex}@example.com",
                hashed_password=hash_password("Old-password-42"),
                role="customer",
            )
            db.add(user)
            await db.commit()
            user_id = user.id
            old_access = create_access_token(user_id)
            db.add(
                APIKey(
                    user_id=user_id,
                    name="old",
                    key_prefix="reset-test",
                    key_hash=uuid4().hex * 2,
                )
            )
            await db.commit()

        async def issue():
            digest = hashlib.sha256(uuid4().hex.encode()).hexdigest()
            async with sessions() as db:
                await PasswordResetRepository(db).replace_active_token(
                    PasswordResetToken(
                        user_id=user_id,
                        token_hash=digest,
                        created_at=now,
                        expires_at=now + timedelta(minutes=10),
                    ),
                    now,
                )

        await asyncio.wait_for(asyncio.gather(issue(), issue()), timeout=20)
        async with sessions() as db:
            active = list(
                (
                    await db.scalars(
                        select(PasswordResetToken).where(
                            PasswordResetToken.user_id == user_id,
                            PasswordResetToken.consumed_at.is_(None),
                        )
                    )
                ).all()
            )
            assert len(active) == 1
            digest = active[0].token_hash

        async def consume():
            async with sessions() as db:
                return await PasswordResetRepository(db).consume_and_change_password(
                    digest, datetime.now(UTC), hash_password("New-password-42")
                )

        results = await asyncio.wait_for(
            asyncio.gather(consume(), consume()), timeout=20
        )
        assert sorted(results) == [False, True]
        async with sessions() as db:
            user = await db.get(User, user_id)
            assert user.token_version == 1
            assert verify_password("New-password-42", user.hashed_password)
            assert not verify_password("Old-password-42", user.hashed_password)
            key = await db.scalar(select(APIKey).where(APIKey.user_id == user_id))
            assert key.revoked_at is not None
            with pytest.raises(HTTPException) as error:
                await get_current_user(token=old_access, api_key=None, db=db)
            assert error.value.status_code == 401
    finally:
        if user_id is not None:
            async with sessions() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
        await engine.dispose()
