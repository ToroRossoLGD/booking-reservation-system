import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.models.api_key import APIKey
from app.models.user import User
from app.services.session_service import SessionService


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__, APIKey.__table__])
    with Session(engine, expire_on_commit=False) as session:
        users = [
            User(
                id=i,
                email=f"user{i}@example.com",
                hashed_password="unchanged",
                role="customer",
            )
            for i in (1, 2)
        ]
        session.add_all(users)
        session.flush()
        keys = [
            APIKey(
                user_id=i, name="integration", key_prefix=str(i), key_hash=str(i) * 64
            )
            for i in (1, 2)
        ]
        old = APIKey(
            user_id=1,
            name="revoked",
            key_prefix="old",
            key_hash="3" * 64,
            revoked_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        session.add_all([*keys, old])
        session.commit()
        db = MagicMock()
        for method in ("scalar", "execute", "commit", "rollback"):
            setattr(db, method, AsyncMock(side_effect=getattr(session, method)))
        yield db, session, users, keys, old
    engine.dispose()


@pytest.mark.asyncio
async def test_revocation_invalidates_old_tokens_and_only_own_active_keys(store):
    db, session, users, keys, old = store
    await SessionService(db).revoke_all(users[0])
    session.expire_all()
    assert users[0].token_version == 1
    assert users[0].hashed_password == "unchanged"
    assert keys[0].revoked_at is not None
    assert old.revoked_at.year == 2025
    assert keys[1].revoked_at is None
    with pytest.raises(HTTPException) as denied:
        await get_current_user(
            token=create_access_token(1, token_version=0), api_key=None, db=db
        )
    assert denied.value.status_code == 401
    for user_id, version in [(1, 1), (2, 0)]:
        user = await get_current_user(
            token=create_access_token(user_id, token_version=version),
            api_key=None,
            db=db,
        )
        assert user.id == user_id


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_both_session_and_keys(store):
    db, session, users, keys, _ = store
    db.commit.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        await SessionService(db).revoke_all(users[0])
    session.expire_all()
    assert users[0].token_version == 0
    assert keys[0].revoked_at is None
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_api_key_stops_authenticating_after_revocation(store):
    db, session, users, keys, _ = store
    raw_key = "brs_test_secret"
    keys[0].key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    session.commit()
    assert (await get_current_user(token=None, api_key=raw_key, db=db)).id == 1
    await SessionService(db).revoke_all(users[0])
    with pytest.raises(HTTPException) as denied:
        await get_current_user(token=None, api_key=raw_key, db=db)
    assert denied.value.status_code == 401


@pytest.mark.asyncio
async def test_stale_authenticated_request_cannot_revoke_new_sessions(store):
    db, _, users, _, _ = store
    stale = User(id=1, token_version=0)
    await SessionService(db).revoke_all(users[0])
    with pytest.raises(HTTPException) as denied:
        await SessionService(db).revoke_all(stale)
    assert denied.value.status_code == 401
    assert users[0].token_version == 1


@pytest.mark.asyncio
async def test_deleted_account_is_rejected_without_commit(store):
    db, _, _, _, _ = store
    with pytest.raises(HTTPException) as denied:
        await SessionService(db).revoke_all(User(id=999, token_version=0))
    assert denied.value.status_code == 401
    db.commit.assert_not_awaited()
