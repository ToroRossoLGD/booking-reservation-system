from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from starlette.requests import Request

from app.core import auth_rate_limit
from app.core import property_rate_limit as limits
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.user import User

PATHS = [
    "/properties/1/rental-inquiries",
    "/properties/2/sale-inquiries",
    "/rental-inquiries/1/messages",
    "/sale-inquiries/2/messages",
    "/properties/1/reports",
    "/owner/properties/1/photos",
]


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, "PROPERTY_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    counter = AsyncMock(return_value=[1, 60000])
    monkeypatch.setattr(auth_rate_limit.redis_client, "eval", counter)
    user = User(
        id=42,
        email="owner@example.com",
        role="owner",
        token_version=0,
        email_verified_at=datetime.now(UTC),
    )

    async def db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield counter, user
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def request(path, host="192.0.2.1", method="POST", root=""):
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
@pytest.mark.parametrize("path", PATHS)
async def test_ip_policy_covers_proxy_prefix_and_trailing_slash(setup, path):
    counter, _ = setup
    for candidate, root in [(path, ""), (path + "/", ""), ("/api" + path, "/api")]:
        assert (
            await limits.enforce_property_ip_limit(request(candidate, root=root))
            is None
        )
    assert (
        counter.await_args_list[0].args
        == counter.await_args_list[1].args
        == counter.await_args_list[2].args
    )


@pytest.mark.asyncio
async def test_ids_offer_type_and_ip_rotation_do_not_reset_account_budget(setup):
    counter, user = setup
    await limits.limit_property_account(request(PATHS[0]), user)
    await limits.limit_property_account(
        request("/properties/999/sale-inquiries", "203.0.113.1"), user
    )
    assert counter.await_args_list[0].args == counter.await_args_list[1].args
    key = counter.await_args.args[2]
    assert key == limits.account_key("inquiry", 42)
    assert user.email not in key
    assert limits.account_key("inquiry", 42) != limits.account_key("inquiry", 43)
    assert limits.account_key("inquiry", 42) != limits.account_key("message", 42)


@pytest.mark.parametrize("path", PATHS)
def test_account_limits_block_each_write_before_business_logic(setup, path):
    counter, _ = setup
    counter.side_effect = [[1, 60000], [0, 45001]]
    response = TestClient(app).post(
        path, json={}, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "46"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert counter.await_count == 2
    assert ":account:" in counter.await_args.args[2]


def test_ip_rejection_precedes_multipart_parsing(setup):
    counter, _ = setup
    counter.return_value = [0, 30000]
    with patch("starlette.formparsers.MultiPartParser.parse", new=AsyncMock()) as parse:
        response = TestClient(app).post(
            PATHS[-1], files={"file": ("photo.png", b"data", "image/png")}
        )
    assert response.status_code == 429
    parse.assert_not_awaited()
    assert counter.await_count == 1


def test_verified_session_and_api_keys_use_same_account_counter(setup):
    counter, user = setup
    app.dependency_overrides.pop(get_current_user)
    counter.side_effect = [[1, 60000], [0, 30000]] * 3
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
            {"Authorization": "Bearer " + create_access_token(user.id)},
            {"X-API-Key": "test-key-one"},
            {"X-API-Key": "test-key-two"},
        ]:
            assert (
                TestClient(app).post(PATHS[2], json={}, headers=headers).status_code
                == 429
            )
    keys = [call.args[2] for call in counter.await_args_list[1::2]]
    assert keys == [limits.account_key("message", user.id)] * 3


def test_invalid_session_cannot_select_an_account_budget(setup):
    counter, _ = setup
    app.dependency_overrides.pop(get_current_user)
    response = TestClient(app).post(
        PATHS[2], json={}, headers={"Authorization": "Bearer invalid"}
    )
    assert response.status_code == 401
    assert counter.await_count == 1
    assert ":account:" not in counter.await_args.args[2]


def test_below_limit_reaches_existing_business_rules(setup):
    counter, _ = setup
    with patch(
        "app.api.routers.rental_inquiries.RentalMessageService.send",
        new=AsyncMock(side_effect=HTTPException(409, "Conversation closed")),
    ) as send:
        response = TestClient(app).post(
            PATHS[2],
            json={"request_id": str(uuid4()), "body": "Is Saturday available?"},
        )
    assert response.status_code == 409
    send.assert_awaited_once()
    assert counter.await_count == 2


@pytest.mark.parametrize("kind", ["rental", "sale"])
@pytest.mark.parametrize("action", ["reply", "propose"])
def test_owner_reply_and_viewing_forms_share_chat_limits(setup, kind, action):
    counter, user = setup
    counter.side_effect = [[1, 60000], [0, 30000]]
    data = {"action": action, "version": 1, "owner_reply": "Saturday is available."}
    if action == "propose":
        data["viewing_at"] = "2035-10-01T12:00:00Z"
    response = TestClient(app).patch(f"/{kind}-inquiries/1", json=data)
    assert response.status_code == 429
    assert counter.await_args.args[2] == limits.account_key("message", user.id)


@pytest.mark.parametrize("action", ["close", "withdraw", "confirm", "decline"])
def test_inquiry_management_reaches_business_rules_even_when_limiter_is_down(
    setup, action
):
    counter, _ = setup
    counter.side_effect = ConnectionError("offline")
    with patch(
        "app.api.routers.rental_inquiries.RentalInquiryService.update",
        new=AsyncMock(side_effect=HTTPException(409, "Version conflict")),
    ) as update:
        response = TestClient(app).patch(
            "/rental-inquiries/1", json={"action": action, "version": 1}
        )
    assert response.status_code == 409
    update.assert_awaited_once()
    counter.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", PATHS[2]),
        ("POST", "/rental-inquiries/1/messages/read"),
        ("PATCH", "/sale-inquiries/1"),
        ("DELETE", "/owner/properties/1/photos/2"),
        ("POST", "/stays/1/cancel"),
        ("OPTIONS", PATHS[0]),
    ],
)
async def test_reads_cancellation_and_management_are_not_throttled(setup, method, path):
    counter, _ = setup
    assert await limits.enforce_property_ip_limit(request(path, method=method)) is None
    counter.assert_not_awaited()


@pytest.mark.asyncio
async def test_production_and_demo_cannot_disable_limits(setup, monkeypatch):
    counter, _ = setup
    monkeypatch.setattr(settings, "PROPERTY_RATE_LIMIT_ENABLED", False)
    await limits.enforce_property_ip_limit(request(PATHS[0]))
    counter.assert_not_awaited()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    await limits.enforce_property_ip_limit(request(PATHS[0]))
    counter.assert_awaited_once()


@pytest.mark.parametrize("account_failure", [False, True])
def test_redis_failures_close_writes_without_leaking_details(
    setup, account_failure, caplog
):
    counter, _ = setup
    error = ConnectionError("private-host secret-token")
    counter.side_effect = [[1, 60000], error] if account_failure else error
    client = TestClient(app)
    response = client.post(PATHS[0], json={})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert "Property rate limiter unavailable" in caplog.text
    assert "secret-token" not in caplog.text + response.text
    assert client.get("/health").status_code == 200
