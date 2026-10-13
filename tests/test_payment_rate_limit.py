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
from app.services.payment_service import PaymentService
from app.services.stripe_service import StripeService

PATHS = ["/payments/reservations/1/pay", "/payments/reservations/2/checkout"]


@pytest.mark.parametrize("action", ["pay", "checkout"])
def test_smoke_invalid_ids_count_without_payment_side_effects(setup, action):
    counter, _ = setup
    with (
        patch.object(PaymentService, "pay_for_reservation", new=AsyncMock()) as pay,
        patch.object(StripeService, "create_checkout", new=AsyncMock()) as checkout,
    ):
        response = TestClient(app).post(f"/payments/reservations/invalid/{action}")
        assert response.status_code == 422
        assert counter.await_count == 2
        pay.assert_not_awaited()
        checkout.assert_not_awaited()


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    counter = AsyncMock(return_value=[1, 60000])
    monkeypatch.setattr(auth_rate_limit.redis_client, "eval", counter)
    user = User(id=42, email="payment@example.com", role="customer", token_version=0)

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
async def test_routes_ids_and_normalized_paths_share_ip_budget(setup):
    counter, _ = setup
    for path in PATHS + ["/payments/reservations/999/pay"]:
        for candidate, root in [(path, ""), (path + "/", ""), ("/api" + path, "/api")]:
            assert (
                await limits.enforce_legacy_write_ip_limit(request(candidate, root))
                is None
            )
    assert all(call.args == counter.await_args.args for call in counter.await_args_list)


@pytest.mark.asyncio
async def test_account_budget_spans_routes_and_ips_but_not_users(setup):
    counter, user = setup
    await limits.limit_legacy_write_account(request(PATHS[0]), user)
    await limits.limit_legacy_write_account(request(PATHS[1], host="203.0.113.1"), user)
    assert counter.await_args_list[0].args == counter.await_args_list[1].args
    key = counter.await_args.args[2]
    assert counter.await_args.args[3:] == (5, 900000)
    user.id = 43
    await limits.limit_legacy_write_account(request(PATHS[0]), user)
    assert counter.await_args.args[2] != key


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("stage", ["ip", "account"])
def test_rejection_prevents_payment_side_effects(setup, path, stage):
    counter, _ = setup
    counter.side_effect = [[0, 2501]] if stage == "ip" else [[1, 60000], [0, 2501]]
    with (
        patch.object(PaymentService, "pay_for_reservation", new=AsyncMock()) as pay,
        patch.object(StripeService, "create_checkout", new=AsyncMock()) as checkout,
    ):
        response = TestClient(app).post(
            path, headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "3"
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Request-ID"]
        assert (
            response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        )
        pay.assert_not_awaited()
        checkout.assert_not_awaited()


@pytest.mark.parametrize("path", PATHS)
def test_ip_rejection_precedes_authentication(setup, path):
    counter, _ = setup
    app.dependency_overrides.pop(get_current_user)
    counter.return_value = [0, 60000]
    assert TestClient(app).post(path).status_code == 429
    counter.assert_awaited_once()


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("stage", ["ip", "account"])
def test_redis_failure_blocks_payment_calls(setup, path, stage):
    counter, _ = setup
    error = ConnectionError("private Redis configuration")
    counter.side_effect = error if stage == "ip" else [[1, 60000], error]
    with (
        patch.object(PaymentService, "pay_for_reservation", new=AsyncMock()) as pay,
        patch.object(StripeService, "create_checkout", new=AsyncMock()) as checkout,
    ):
        response = TestClient(app).post(path)
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "30"
        assert "private" not in response.text
        pay.assert_not_awaited()
        checkout.assert_not_awaited()


@pytest.mark.parametrize(
    "path,service,method",
    [
        (PATHS[0], PaymentService, "pay_for_reservation"),
        (PATHS[1], StripeService, "create_checkout"),
    ],
)
def test_service_ownership_rejection_is_preserved(setup, path, service, method):
    with patch.object(
        service,
        method,
        new=AsyncMock(side_effect=HTTPException(403, "Not your reservation")),
    ) as write:
        assert TestClient(app).post(path).status_code == 403
        write.assert_awaited_once()


def test_webhook_reaches_signature_validation_during_limiter_outage(setup):
    counter, _ = setup
    counter.side_effect = ConnectionError("offline")
    app.dependency_overrides.pop(get_current_user)
    with patch.object(
        StripeService,
        "handle_webhook",
        new=AsyncMock(side_effect=HTTPException(400, "Invalid signature")),
    ) as webhook:
        response = TestClient(app).post(
            "/payments/stripe/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "invalid"},
        )
        assert response.status_code == 400
        webhook.assert_awaited_once_with(b"{}", "invalid")
    counter.assert_not_awaited()


def test_payment_read_is_available_during_outage(setup):
    counter, _ = setup
    counter.side_effect = ConnectionError("offline")
    with patch.object(
        PaymentService,
        "get_reservation_payment",
        new=AsyncMock(side_effect=HTTPException(404, "Missing payment")),
    ) as read:
        assert TestClient(app).get("/payments/reservations/1").status_code == 404
        read.assert_awaited_once()
    counter.assert_not_awaited()


@pytest.mark.parametrize("path", PATHS)
def test_production_cannot_disable_limits(setup, monkeypatch, path):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", False)
    assert limits.policy_for(request(path)) is not None
