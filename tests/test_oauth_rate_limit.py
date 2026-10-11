from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from starlette.requests import Request

from app.core import auth_rate_limit as limiter
from app.core.config import settings
from app.main import app
from app.services.auth_service import AuthService


@pytest.fixture
def counter(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    fake = AsyncMock(return_value=[1, 60000])
    monkeypatch.setattr(limiter.redis_client, "eval", fake)
    return fake


@pytest.mark.asyncio
@pytest.mark.parametrize("path", limiter.OAUTH_POLICIES)
async def test_oauth_paths_normalize_before_consuming_independent_budgets(
    counter, path
):
    for candidate, root in [(path, ""), (path + "/", ""), ("/api" + path, "/api")]:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": candidate,
                "root_path": root,
                "headers": [],
                "client": ("192.0.2.1", 1234),
            }
        )
        assert await limiter.enforce_auth_rate_limit(request) is None
    assert len(counter.await_args_list) == 3
    assert all(call.args == counter.await_args.args for call in counter.await_args_list)
    action, limit, seconds = limiter.OAUTH_POLICIES[path]
    assert counter.await_args.args[2:] == (
        limiter.bucket_key(action, "192.0.2.1"),
        limit,
        seconds * 1000,
    )


@pytest.mark.parametrize("path", limiter.OAUTH_POLICIES)
@pytest.mark.parametrize("outage", [False, True])
def test_blocked_browser_never_reaches_google_or_exposes_callback_data(
    counter, monkeypatch, path, outage
):
    if outage:
        counter.side_effect = ConnectionError("private Redis detail")
    else:
        counter.return_value = [0, 1234]
    start = Mock()
    callback = AsyncMock()
    monkeypatch.setattr(AuthService, "create_google_authorization", start)
    monkeypatch.setattr(AuthService, "login_with_google", callback)
    response = TestClient(app).get(
        path + "?code=private-code&state=private-state",
        headers={"Accept": "text/html", "Cookie": "google_oauth_state=private-cookie"},
        follow_redirects=False,
    )
    assert response.status_code == (503 if outage else 429)
    assert response.headers["Retry-After"] == ("30" if outage else "2")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert "text/html" in response.headers["Content-Type"]
    assert "private" not in response.text
    assert "Vrati se na prijavu" in response.text
    assert 'rel="noreferrer"' in response.text
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "Max-Age=0" in response.headers["Set-Cookie"]
    assert "Path=/auth/google" in response.headers["Set-Cookie"]
    start.assert_not_called()
    callback.assert_not_awaited()


def test_json_clients_keep_machine_readable_error_and_cors(counter):
    counter.return_value = [0, 60000]
    response = TestClient(app).get(
        "/auth/google/callback",
        headers={"Accept": "application/json", "Origin": "http://localhost:5173"},
        follow_redirects=False,
    )
    assert response.status_code == 429
    assert "detail" in response.json()
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert response.headers["Retry-After"] == "60"


def test_allowed_start_keeps_existing_redirect_and_oauth_cookie(counter, monkeypatch):
    monkeypatch.setattr(
        AuthService,
        "create_google_authorization",
        lambda: ("https://accounts.google.com/example", "test-state"),
    )
    response = TestClient(app).get("/auth/google/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == "https://accounts.google.com/example"
    assert "google_oauth_state=test-state" in response.headers["Set-Cookie"]
    counter.assert_awaited_once()


def test_method_mismatch_does_not_consume_oauth_budget(counter):
    response = TestClient(app).post("/auth/google/callback")
    assert response.status_code == 405
    counter.assert_not_awaited()
