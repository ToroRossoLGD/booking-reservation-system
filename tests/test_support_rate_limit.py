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
from app.services.support_ticket_service import SupportTicketService

PATHS = [
    "/support/tickets",
    "/support/tickets/1/messages",
    "/support/admin/tickets/2/messages",
]


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    counter = AsyncMock(return_value=[1, 60000])
    monkeypatch.setattr(auth_rate_limit.redis_client, "eval", counter)
    user = User(id=42, email="support@example.com", role="admin", token_version=0)

    async def database():
        yield AsyncMock()

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield counter, user
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def request(path, root="", host="192.0.2.1"):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "root_path": root,
            "headers": [],
            "client": (host, 1234),
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", PATHS)
async def test_proxy_and_trailing_slash_share_ip_budget(setup, path):
    counter, _ = setup
    for candidate, root in [(path, ""), (path + "/", ""), ("/api" + path, "/api")]:
        assert (
            await limits.enforce_legacy_write_ip_limit(request(candidate, root)) is None
        )
    assert all(call.args == counter.await_args.args for call in counter.await_args_list)


@pytest.mark.parametrize("path", PATHS)
def test_account_limit_blocks_all_support_writes_with_retry_metadata(setup, path):
    counter, _ = setup
    counter.side_effect = [[1, 60000], [0, 2501]]
    response = TestClient(app).post(
        path, json={}, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "3"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert counter.await_count == 2


@pytest.mark.asyncio
async def test_messages_share_account_budget_across_tickets_roles_and_ips(setup):
    counter, user = setup
    await limits.limit_legacy_write_account(request(PATHS[1]), user)
    await limits.limit_legacy_write_account(
        request("/support/admin/tickets/999/messages", host="203.0.113.1"), user
    )
    assert counter.await_args_list[0].args == counter.await_args_list[1].args
    message_key = counter.await_args.args[2]
    await limits.limit_legacy_write_account(request(PATHS[0]), user)
    assert counter.await_args.args[2] != message_key
    user.id = 43
    await limits.limit_legacy_write_account(request(PATHS[1]), user)
    assert counter.await_args.args[2] != message_key


def test_ip_rejection_precedes_invalid_json_and_authentication(setup):
    counter, _ = setup
    app.dependency_overrides.pop(get_current_user)
    counter.return_value = [0, 60000]
    response = TestClient(app).post(
        PATHS[0], content=b"not-json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 429
    counter.assert_awaited_once()


def test_customer_cannot_use_admin_message_route_with_available_budget(setup):
    _, user = setup
    user.role = "customer"
    with patch.object(
        SupportTicketService, "add_admin_message", new=AsyncMock()
    ) as write:
        response = TestClient(app).post(PATHS[2], json={"message": "hello"})
    assert response.status_code == 403
    write.assert_not_awaited()


def test_ownership_rejection_remains_after_limiter(setup):
    _, user = setup
    user.role = "customer"
    with patch.object(
        SupportTicketService,
        "add_customer_message",
        new=AsyncMock(side_effect=HTTPException(403, "Not your ticket")),
    ) as write:
        assert (
            TestClient(app).post(PATHS[1], json={"message": "hello"}).status_code == 403
        )
        write.assert_awaited_once()


@pytest.mark.parametrize("stage", ["ip", "account"])
def test_redis_failure_blocks_support_writes(setup, stage):
    counter, _ = setup
    error = ConnectionError("private Redis configuration")
    counter.side_effect = error if stage == "ip" else [[1, 60000], error]
    response = TestClient(app).post(PATHS[0], json={})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert "private" not in response.text


def test_ticket_closure_is_available_during_limiter_outage(setup):
    counter, _ = setup
    counter.side_effect = ConnectionError("offline")
    with patch.object(
        SupportTicketService,
        "close_my_ticket",
        new=AsyncMock(side_effect=HTTPException(404, "Missing ticket")),
    ) as close:
        assert TestClient(app).patch("/support/tickets/1/close").status_code == 404
        close.assert_awaited_once()
    counter.assert_not_awaited()
