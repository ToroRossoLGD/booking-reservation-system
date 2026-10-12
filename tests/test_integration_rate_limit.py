from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from starlette.requests import Request

from app.core import auth_rate_limit
from app.core import legacy_write_rate_limit as limits
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.user import User

WRITES = [
    ("POST", "/auth/api-keys"),
    ("POST", "/venues/1/webhooks"),
    ("PUT", "/venues/2/webhooks/3"),
    ("POST", "/venues/2/webhooks/deliveries/4/retry"),
]


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    counter = AsyncMock(return_value=[1, 60000])
    monkeypatch.setattr(auth_rate_limit.redis_client, "eval", counter)
    user = User(id=42, email="owner@example.com", role="owner", token_version=0)

    async def database():
        yield AsyncMock()

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield counter, user
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def request(method, path, root="", host="192.0.2.1"):
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "root_path": root,
            "headers": [],
            "client": (host, 1234),
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", WRITES)
async def test_route_normalization_and_ip_policy(setup, method, path):
    counter, _ = setup
    for candidate, root in [(path, ""), (path + "/", ""), ("/api" + path, "/api")]:
        assert (
            await limits.enforce_legacy_write_ip_limit(request(method, candidate, root))
            is None
        )
    assert all(call.args == counter.await_args.args for call in counter.await_args_list)


@pytest.mark.parametrize("method,path", WRITES)
def test_account_rejection_precedes_validation_and_writes(setup, method, path):
    counter, _ = setup
    counter.side_effect = [[1, 60000], [0, 1201]]
    response = TestClient(app).request(
        method, path, json={}, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "2"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert counter.await_count == 2
    assert ":account:" in counter.await_args.args[2]


@pytest.mark.asyncio
async def test_changing_venue_or_ip_cannot_reset_account_write_budget(setup):
    counter, user = setup
    await limits.limit_legacy_write_account(request("POST", "/venues/1/webhooks"), user)
    await limits.limit_legacy_write_account(
        request("PUT", "/venues/99/webhooks/77", host="203.0.113.1"), user
    )
    assert counter.await_args_list[0].args == counter.await_args_list[1].args
    assert "owner@example.com" not in counter.await_args.args[2]
    assert limits.account_key("webhook-write", 42) != limits.account_key(
        "webhook-write", 43
    )
    assert limits.account_key("webhook-write", 42) != limits.account_key(
        "webhook-retry", 42
    )


@pytest.mark.parametrize("stage", ["ip", "account"])
def test_redis_outage_fails_closed_with_redacted_error(setup, stage, caplog):
    counter, _ = setup
    error = ConnectionError("private-redis-secret")
    counter.side_effect = error if stage == "ip" else [[1, 60000], error]
    response = TestClient(app).post("/auth/api-keys", json={})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert "private-redis-secret" not in response.text + caplog.text
    assert "Legacy write rate limiter unavailable" in caplog.text


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/auth/api-keys"),
        ("DELETE", "/auth/api-keys/1"),
        ("DELETE", "/venues/1/webhooks/2"),
        ("POST", "/venues/1/webhooks/2/rotate-secret"),
        ("GET", "/venues/1/webhooks/deliveries/history"),
        ("POST", "/payments/webhook"),
    ],
)
@pytest.mark.asyncio
async def test_reads_shutdown_rotation_and_provider_callbacks_are_not_throttled(
    setup, method, path
):
    counter, user = setup
    req = request(method, path)
    assert await limits.enforce_legacy_write_ip_limit(req) is None
    await limits.limit_legacy_write_account(req, user)
    counter.assert_not_awaited()


def test_bearer_and_api_keys_share_account_budget(setup):
    counter, user = setup
    app.dependency_overrides.pop(get_current_user)
    counter.side_effect = [[1, 60000], [0, 60000]] * 2
    with (
        patch(
            "app.core.dependencies.UserRepository.get_by_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.core.dependencies.APIKeyService.authenticate",
            new=AsyncMock(return_value=user),
        ),
    ):
        for headers in [
            {"Authorization": "Bearer " + create_access_token(42)},
            {"X-API-Key": "test-key"},
        ]:
            assert (
                TestClient(app)
                .post("/auth/api-keys", json={}, headers=headers)
                .status_code
                == 429
            )
    assert counter.await_args_list[1].args == counter.await_args_list[3].args


@pytest.mark.asyncio
async def test_production_cannot_disable_limit(setup, monkeypatch):
    counter, _ = setup
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", False)
    req = request("POST", "/auth/api-keys")
    assert await limits.enforce_legacy_write_ip_limit(req) is None
    counter.assert_not_awaited()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    await limits.enforce_legacy_write_ip_limit(req)
    counter.assert_awaited_once()


def test_unauthenticated_call_does_not_consume_account_budget(setup):
    counter, _ = setup
    app.dependency_overrides.pop(get_current_user)
    assert TestClient(app).post("/auth/api-keys", json={}).status_code == 401
    assert counter.await_count == 1


@pytest.mark.asyncio
async def test_limit_boundaries_preserve_other_actions(setup):
    counter, user = setup
    counts = {}

    async def consume(script, number, key, maximum, ttl):
        current = counts.get(key, 0)
        if current >= maximum:
            return [0, ttl]
        counts[key] = current + 1
        return [1, ttl]

    counter.side_effect = consume
    req = request("POST", "/auth/api-keys")
    for _ in range(5):
        await limits.limit_legacy_write_account(req, user)
    with pytest.raises(HTTPException) as denied:
        await limits.limit_legacy_write_account(req, user)
    assert denied.value.status_code == 429
    await limits.limit_legacy_write_account(request("POST", "/venues/1/webhooks"), user)
