from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.api_key import APIKey
from app.models.user import User
from app.provision_user import change_role, parser
from app.schemas.auth import UserCreate
from app.services.auth_service import AuthService


@pytest.mark.parametrize(
    "extra", [{"role": "admin"}, {"role": "owner"}, {"is_admin": True}]
)
def test_public_registration_rejects_privilege_input_without_writes(extra):
    db = AsyncMock()

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        response = TestClient(app).post(
            "/auth/register",
            json={"email": "new@example.com", "password": "SamplePassword123", **extra},
        )
        assert response.status_code == 422
        db.execute.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["customer", "admin", "owner"])
async def test_registration_service_always_creates_customer_even_if_validation_bypassed(
    role,
):
    service = AuthService(AsyncMock())
    service.user_repository.get_by_email = AsyncMock(return_value=None)
    service.user_repository.create = AsyncMock(side_effect=lambda user: user)
    data = UserCreate.model_construct(
        email="new@example.com", password="SamplePassword123", role=role
    )
    user = await service.register(data)
    assert user.role == "customer"
    assert user.hashed_password != data.password


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__, APIKey.__table__])
    with Session(engine, expire_on_commit=False) as session:
        user = User(
            id=1,
            email="owner@example.com",
            hashed_password="test",
            role="customer",
            token_version=0,
        )
        session.add(user)
        session.flush()
        key = APIKey(user_id=1, name="Old key", key_prefix="test", key_hash="a" * 64)
        session.add(key)
        session.commit()
        db = MagicMock()
        for method in ("scalar", "execute", "commit", "rollback"):
            setattr(db, method, AsyncMock(side_effect=getattr(session, method)))
        yield db, session, user, key
    engine.dispose()


@pytest.mark.asyncio
async def test_operator_preview_apply_retry_and_demotion(store):
    db, session, user, key = store
    old_token = create_access_token(subject=1, token_version=0)
    assert not (await change_role(db, 1, user.email, "customer", "owner"))["applied"]
    assert (
        user.role == "customer" and user.token_version == 0 and key.revoked_at is None
    )
    result = await change_role(db, 1, user.email, "customer", "owner", apply=True)
    session.refresh(key)
    assert result["applied"] and user.role == "owner"
    assert user.token_version == 1 and key.revoked_at is not None
    with pytest.raises(HTTPException) as denied:
        await get_current_user(token=old_token, api_key=None, db=db)
    assert denied.value.status_code == 401
    with pytest.raises(ValueError, match="expected-role"):
        await change_role(db, 1, user.email, "customer", "admin", apply=True)
    await db.rollback()
    assert not (await change_role(db, 1, user.email, "owner", "owner", apply=True))[
        "changed"
    ]
    assert user.token_version == 1
    await change_role(db, 1, user.email, "owner", "admin", apply=True)
    await change_role(db, 1, user.email, "admin", "customer", apply=True)
    assert user.role == "customer" and user.token_version == 3


@pytest.mark.asyncio
async def test_operator_rejects_wrong_identity_and_rolls_back_commit_failure(store):
    db, session, user, key = store
    for user_id, email in [(99, user.email), (1, "different@example.com")]:
        with pytest.raises(ValueError, match="does not match"):
            await change_role(db, user_id, email, "customer", "admin", apply=True)
        await db.rollback()
    db.commit.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        await change_role(db, 1, user.email, "customer", "admin", apply=True)
    await db.rollback()
    session.refresh(key)
    assert (
        user.role == "customer" and user.token_version == 0 and key.revoked_at is None
    )


def test_operator_requires_explicit_apply_and_expected_role():
    args = ["--user-id", "1", "--email", "owner@example.com", "--role", "owner"]
    with pytest.raises(SystemExit):
        parser().parse_args(args)
    assert not parser().parse_args(args + ["--expected-role", "customer"]).apply
