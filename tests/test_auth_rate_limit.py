import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from starlette.requests import Request

from app.core import auth_rate_limit as limiter
from app.core.config import settings
from app.main import app


@pytest.fixture
def counter(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "test")
    fake = AsyncMock(return_value=[1, 60000])
    monkeypatch.setattr(limiter.redis_client, "eval", fake)
    return fake


def request(path="/auth/login", method="POST", host="192.0.2.1", root=""):
    return Request(
        {
            "type": "http",
            "path": path,
            "root_path": root,
            "method": method,
            "headers": [(b"x-forwarded-for", b"198.51.100.1")],
            "client": (host, 12345),
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", list(limiter.POLICIES))
async def test_all_auth_policies_share_trailing_slash_and_proxy_path_budget(
    counter, path
):
    for candidate, root in [(path, ""), (path + "/", ""), ("/api" + path, "/api")]:
        assert (
            await limiter.enforce_auth_rate_limit(request(candidate, root=root)) is None
        )
    calls = counter.await_args_list
    assert calls[0].args == calls[1].args == calls[2].args
    action, limit, seconds = limiter.POLICIES[path]
    assert calls[0].args[2:] == (
        limiter.bucket_key(action, "192.0.2.1"),
        limit,
        seconds * 1000,
    )


@pytest.mark.asyncio
async def test_raw_forwarding_headers_cannot_change_key(counter):
    first = request()
    second = request()
    second.scope["headers"] = [
        (b"x-forwarded-for", b"203.0.113.7"),
        (b"x-real-ip", b"203.0.113.8"),
    ]
    await limiter.enforce_auth_rate_limit(first)
    await limiter.enforce_auth_rate_limit(second)
    assert counter.await_args_list[0].args == counter.await_args_list[1].args
    await limiter.enforce_auth_rate_limit(request(host="192.0.2.2"))
    assert counter.await_args_list[0].args[2] != counter.await_args_list[2].args[2]


def test_hashed_keys_normalize_ipv4_and_ipv6_without_raw_addresses():
    assert limiter.bucket_key("login", "::ffff:192.0.2.1") == limiter.bucket_key(
        "login", "192.0.2.1"
    )
    assert limiter.bucket_key("login", "2001:db8:1:2::1") == limiter.bucket_key(
        "login", "2001:0db8:0001:0002::abcd"
    )
    assert limiter.bucket_key("login", "2001:db8:1:3::1") != limiter.bucket_key(
        "login", "2001:db8:1:2::1"
    )
    assert "192.0.2.1" not in limiter.bucket_key("login", "192.0.2.1")
    assert limiter.bucket_key("login", "192.0.2.1") != limiter.bucket_key(
        "signup", "192.0.2.1"
    )


@pytest.mark.asyncio
async def test_retry_after_rounds_up_and_never_returns_zero(counter):
    counter.return_value = [0, 1001]
    response = await limiter.enforce_auth_rate_limit(request())
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "2"
    assert response.headers["Cache-Control"] == "no-store"
    counter.return_value = [0, 0]
    assert (await limiter.enforce_auth_rate_limit(request())).headers[
        "Retry-After"
    ] == "1"


@pytest.mark.asyncio
async def test_production_cannot_disable_limits(counter, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", False)
    assert await limiter.enforce_auth_rate_limit(request()) is None
    counter.assert_not_awaited()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    await limiter.enforce_auth_rate_limit(request())
    counter.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,method",
    [
        ("/health", "GET"),
        ("/auth/me", "GET"),
        ("/auth/login", "OPTIONS"),
        ("/auth/login", "GET"),
        ("/properties", "GET"),
    ],
)
async def test_other_routes_do_not_consume_auth_budgets(counter, path, method):
    assert await limiter.enforce_auth_rate_limit(request(path, method)) is None
    counter.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_failure_is_closed_and_redacted(counter, caplog):
    counter.side_effect = ConnectionError("private-redis-host secret-token")
    response = await limiter.enforce_auth_rate_limit(request())
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert "Auth rate limiter unavailable" in caplog.text
    assert "private-redis-host" not in caplog.text
    assert "secret-token" not in json.loads(response.body)["detail"]


def test_http_rejection_runs_before_validation_and_keeps_cors_request_id(counter):
    counter.return_value = [0, 60000]
    client = TestClient(app)
    response = client.post(
        "/auth/login", data={}, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Retry-After" in response.headers["Access-Control-Expose-Headers"]
    assert response.headers["X-Request-ID"]
    assert client.get("/health").status_code == 200
    assert client.get("/auth/me").status_code == 401
    counter.assert_awaited_once()


def test_unavailable_limiter_blocks_auth_but_not_health(counter):
    counter.side_effect = ConnectionError("private")
    client = TestClient(app)
    assert client.post("/auth/register", json={}).status_code == 503
    assert client.get("/health").status_code == 200
