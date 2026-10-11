from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from app.core import auth_rate_limit as shared
from app.core.account_auth_rate_limit import POLICIES, limit_auth_target, target_key
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.email_verification_service import EmailVerificationService
from app.services.password_reset_service import PasswordResetService


@pytest.fixture
def counter(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    counts = {}

    async def consume(script, count, key, limit, milliseconds):
        counts[key] = min(counts.get(key, 0) + 1, limit + 1)
        return [int(counts[key] <= limit), milliseconds]

    fake = AsyncMock(side_effect=consume)
    monkeypatch.setattr(shared.redis_client, "eval", fake)
    return fake


def test_keys_group_case_and_whitespace_without_exposing_identity():
    key = target_key("login", " Person@Example.com ")
    assert key == target_key("login", "person@example.com")
    assert "person" not in key and "example.com" not in key
    assert key != target_key("reset-request", "person@example.com")
    assert key != target_key("login", "another@example.com")


@pytest.mark.asyncio
@pytest.mark.parametrize("action", POLICIES)
async def test_each_budget_blocks_at_boundary_and_keeps_other_targets_available(
    counter, action
):
    limit, seconds = POLICIES[action]
    for _ in range(limit):
        await limit_auth_target(action, "person@example.com")
    with pytest.raises(HTTPException) as error:
        await limit_auth_target(action, "PERSON@example.com ")
    assert error.value.status_code == 429
    assert error.value.headers == {
        "Retry-After": str(seconds),
        "Cache-Control": "no-store",
    }
    await limit_auth_target(action, "other@example.com")


@pytest.mark.asyncio
async def test_redis_failure_is_redacted_and_fails_closed(counter):
    counter.side_effect = ConnectionError("private infrastructure detail")
    with pytest.raises(HTTPException) as error:
        await limit_auth_target("login", "person@example.com")
    assert error.value.status_code == 503
    assert error.value.headers["Retry-After"] == "30"
    assert "private" not in error.value.detail


@pytest.mark.asyncio
async def test_production_cannot_disable_target_budgets(counter, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", False)
    await limit_auth_target("login", "person@example.com")
    counter.assert_not_awaited()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    await limit_auth_target("login", "person@example.com")
    counter.assert_awaited_once()


@pytest.mark.parametrize("action", POLICIES)
def test_routes_share_target_across_ips_and_stop_before_business_logic(
    counter, monkeypatch, action
):
    methods = {
        "login": (AuthService, "login"),
        "reset-request": (PasswordResetService, "request_reset"),
        "verification-request": (EmailVerificationService, "request"),
    }
    service, method = methods[action]
    result = "test-access-token" if action == "login" else {"message": "generic"}
    business = AsyncMock(return_value=result)
    monkeypatch.setattr(service, method, business)

    async def database():
        yield AsyncMock()

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: User(id=42, token_version=0)
    try:
        limit, _ = POLICIES[action]
        responses = []
        for index in range(limit + 1):
            client = TestClient(app, client=(f"192.0.2.{index + 1}", 12345))
            headers = {"Origin": "http://localhost:5173"}
            if action == "login":
                response = client.post(
                    "/auth/login",
                    data={
                        "username": "person@example.com",
                        "password": "example-password",
                    },
                    headers=headers,
                )
            elif action == "reset-request":
                response = client.post(
                    "/auth/password-reset/request",
                    json={"email": "person@example.com"},
                    headers=headers,
                )
            else:
                response = client.post(
                    "/auth/email-verification/request", headers=headers
                )
            responses.append(response)
        assert all(response.status_code == 200 for response in responses[:-1])
        assert responses[-1].status_code == 429
        assert responses[-1].headers["Retry-After"] == "900"
        assert responses[-1].headers["X-Request-ID"]
        assert (
            responses[-1].headers["Access-Control-Allow-Origin"]
            == "http://localhost:5173"
        )
        assert business.await_count == limit
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_resend_requires_authentication_before_consuming_target_budget(counter):
    async def database():
        yield AsyncMock()

    app.dependency_overrides[get_db] = database
    try:
        response = TestClient(app).post(
            "/auth/email-verification/request", json={"user_id": 42}
        )
        assert response.status_code == 401
        assert all(
            not call.args[2].startswith("bookica:auth-target:")
            for call in counter.await_args_list
        )
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_unknown_and_existing_email_attempts_use_same_target_policy(
    counter, monkeypatch
):
    business = AsyncMock(side_effect=HTTPException(401, "Invalid email or password"))
    monkeypatch.setattr(AuthService, "login", business)

    async def database():
        yield AsyncMock()

    app.dependency_overrides[get_db] = database
    try:
        for email in ["unknown@example.com", "existing@example.com"]:
            for index in range(31):
                client = TestClient(app, client=(f"198.51.100.{index + 1}", 12345))
                response = client.post(
                    "/auth/login", data={"username": email, "password": "wrong"}
                )
                assert response.status_code == (401 if index < 30 else 429)
    finally:
        app.dependency_overrides.pop(get_db, None)
