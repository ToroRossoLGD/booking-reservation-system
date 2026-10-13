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
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services.reservation_service import ReservationService

PATHS = [
    ("POST", "/reservations"),
    ("POST", "/reservations/recurring"),
    ("PATCH", "/reservations/123/reschedule"),
]


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    counter = AsyncMock(return_value=[1, 60000])
    monkeypatch.setattr(auth_rate_limit.redis_client, "eval", counter)
    user = User(id=42, email="booking@example.com", role="customer", token_version=0)

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
@pytest.mark.parametrize("method,path", PATHS)
async def test_normalized_paths_share_ip_budget(setup, method, path):
    counter, _ = setup
    for candidate, root in [(path, ""), (path + "/", ""), ("/api" + path, "/api")]:
        assert (
            await limits.enforce_legacy_write_ip_limit(request(method, candidate, root))
            is None
        )
    assert all(call.args == counter.await_args.args for call in counter.await_args_list)


@pytest.mark.parametrize("method,path", PATHS)
def test_account_rejection_includes_retry_metadata(setup, method, path):
    counter, _ = setup
    counter.side_effect = [[1, 60000], [0, 2501]]
    response = TestClient(app).request(
        method, path, json={}, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "3"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert counter.await_count == 2


@pytest.mark.asyncio
async def test_creation_and_reschedule_share_budgets_across_ids_and_ips(setup):
    counter, user = setup
    for method, path in [PATHS[0], PATHS[2], ("PATCH", "/reservations/999/reschedule")]:
        await limits.enforce_legacy_write_ip_limit(request(method, path))
    assert all(call.args == counter.await_args.args for call in counter.await_args_list)
    counter.reset_mock()
    await limits.limit_legacy_write_account(request(*PATHS[0]), user)
    await limits.limit_legacy_write_account(
        request(*PATHS[2], host="203.0.113.1"), user
    )
    assert counter.await_args_list[0].args == counter.await_args_list[1].args
    single_key = counter.await_args.args[2]
    await limits.limit_legacy_write_account(request(*PATHS[1]), user)
    assert counter.await_args.args[2] != single_key
    assert counter.await_args.args[3:] == (2, 900000)
    user.id = 43
    await limits.limit_legacy_write_account(request(*PATHS[0]), user)
    assert counter.await_args.args[2] != single_key


@pytest.mark.parametrize("method,path", PATHS)
def test_ip_rejection_precedes_parsing_and_auth(setup, method, path):
    counter, _ = setup
    app.dependency_overrides.pop(get_current_user)
    counter.return_value = [0, 60000]
    response = TestClient(app).request(
        method, path, content=b"not-json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 429
    counter.assert_awaited_once()


@pytest.mark.parametrize("method,path", PATHS)
@pytest.mark.parametrize("stage", ["ip", "account"])
def test_redis_failure_fails_closed(setup, method, path, stage):
    counter, _ = setup
    error = ConnectionError("private Redis configuration")
    counter.side_effect = error if stage == "ip" else [[1, 60000], error]
    response = TestClient(app).request(method, path, json={})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert "private" not in response.text


@pytest.mark.parametrize(
    "path,service,body",
    [
        ("/reservations/1/cancel", "cancel_reservation", None),
        ("/reservations/series/missing/cancel", "cancel_recurring_reservations", {}),
    ],
)
def test_cancellation_remains_available_during_outage(setup, path, service, body):
    counter, _ = setup
    counter.side_effect = ConnectionError("offline")
    with patch.object(
        ReservationService,
        service,
        new=AsyncMock(side_effect=HTTPException(404, "Missing reservation")),
    ) as cancel:
        assert TestClient(app).patch(path, json=body).status_code == 404
        cancel.assert_awaited_once()
    counter.assert_not_awaited()


def test_reschedule_ownership_check_is_preserved(setup):
    with patch.object(
        ReservationService,
        "reschedule_reservation",
        new=AsyncMock(side_effect=HTTPException(403, "Not your reservation")),
    ) as write:
        response = TestClient(app).patch(
            PATHS[2][1],
            json={
                "start_time": "2030-01-01T10:00:00Z",
                "end_time": "2030-01-01T11:00:00Z",
            },
        )
        assert response.status_code == 403
        write.assert_awaited_once()


@pytest.mark.parametrize("method,path", PATHS)
def test_production_cannot_disable_protection(setup, monkeypatch, method, path):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", False)
    assert limits.policy_for(request(method, path)) is not None


def test_read_quote_and_lifecycle_routes_do_not_consume_budget(setup):
    for method, path in [
        ("GET", "/reservations/my"),
        ("POST", "/reservations/quote"),
        ("PATCH", "/reservations/1/confirm"),
        ("PATCH", "/reservations/1/complete"),
    ]:
        assert limits.policy_for(request(method, path)) is None
