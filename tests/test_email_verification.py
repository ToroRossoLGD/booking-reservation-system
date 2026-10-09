import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings
from app.core.dependencies import get_current_user, require_verified_user
from app.db.session import get_db
from app.main import app
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.services.email_verification_service import MESSAGE, EmailVerificationService
from tests.test_stay_migration import load_migration


@pytest.fixture
def account(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "SMTP_MODE", "plain")
    return User(
        id=5, email="guest@example.com", hashed_password="hash", role="customer"
    )


@pytest.mark.asyncio
async def test_issue_hash_only_with_fragment_and_bound_email(account):
    db = AsyncMock()
    db.add = MagicMock()
    db.scalar.side_effect = [account, None]
    tasks = BackgroundTasks()
    result = await EmailVerificationService(db).request(account, tasks)
    stored = db.add.call_args.args[0]
    recipient, link = tasks.tasks[0].args
    url = urlsplit(link)
    raw = parse_qs(url.fragment)["token"][0]
    assert url.path == "/verify-email" and not url.query
    assert recipient == stored.email == account.email
    assert stored.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert stored.token_hash != raw
    assert stored.expires_at > stored.created_at
    assert result == MESSAGE and raw not in str(result)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("verified", [False, True])
async def test_cooldown_and_verified_account_send_nothing(account, verified):
    if verified:
        account.email_verified_at = datetime.now(UTC)
    db = AsyncMock()
    db.scalar.side_effect = [account, MagicMock(created_at=datetime.now(UTC))]
    tasks = BackgroundTasks()
    assert await EmailVerificationService(db).request(account, tasks) == MESSAGE
    assert not tasks.tasks
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("demo,mode", [(True, "plain"), (False, "disabled")])
async def test_disabled_delivery_preserves_signup_but_blocks_resend(
    account, monkeypatch, demo, mode
):
    monkeypatch.setattr(settings, "DEMO_MODE", demo)
    monkeypatch.setattr(settings, "SMTP_MODE", mode)
    db = AsyncMock()
    service = EmailVerificationService(db)
    assert await service.request(account, BackgroundTasks(), automatic=True) == MESSAGE
    with pytest.raises(HTTPException) as exc:
        await service.request(account, BackgroundTasks())
    assert exc.value.status_code == 503
    db.scalar.assert_not_awaited()


def test_delivery_failure_does_not_log_credentials_or_token(caplog):
    with patch(
        "app.services.email_verification_service.EmailService.send_email",
        side_effect=RuntimeError("private-token user@example.com"),
    ):
        EmailVerificationService.deliver("user@example.com", "private-token")
    assert "delivery failed" in caplog.text
    assert "private-token" not in caplog.text and "user@example.com" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,status",
    [("missing", 400), ("expired", 410), ("consumed", 409), ("changed_email", 409)],
)
async def test_invalid_links_never_verify_account(account, case, status):
    token = EmailVerificationToken(
        user_id=account.id,
        email=account.email,
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    if case == "expired":
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    if case == "consumed":
        token.consumed_at = datetime.now(UTC)
    if case == "changed_email":
        token.email = "old@example.com"
    db = AsyncMock()
    db.scalar.side_effect = [None if case == "missing" else token, account]
    with pytest.raises(HTTPException) as exc:
        await EmailVerificationService(db).confirm("a" * 43)
    assert exc.value.status_code == status
    assert not account.email_verified
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmation_verifies_account_without_changing_sessions(account):
    token = EmailVerificationToken(
        user_id=account.id,
        email=account.email,
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    db = AsyncMock()
    db.scalar.side_effect = [token, account]
    old_version = account.token_version
    await EmailVerificationService(db).confirm("a" * 43)
    assert account.email_verified
    assert account.token_version == old_version
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["customer", "owner", "admin"])
async def test_gate_requires_verification_for_every_role_except_demo(
    account, monkeypatch, role
):
    account.role = role
    with pytest.raises(HTTPException) as exc:
        await require_verified_user(account)
    assert exc.value.status_code == 403
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert await require_verified_user(account) is account
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    account.email_verified_at = datetime.now(UTC)
    assert await require_verified_user(account) is account


def test_api_gates_new_actions_but_allows_me_and_queues_signup_email(account):
    db = AsyncMock()

    async def session():
        yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: account
    try:
        client = TestClient(app)
        assert client.get("/auth/me").json()["email_verified"] is False
        for endpoint in ["stays", "rental-inquiries", "sale-inquiries"]:
            response = client.post(f"/properties/1/{endpoint}", json={})
            assert response.status_code == 403
            assert "/verify-email" in response.json()["detail"]
        db.commit.assert_not_awaited()
        with (
            patch(
                "app.api.routers.auth.AuthService.register",
                new=AsyncMock(return_value=account),
            ),
            patch.object(
                EmailVerificationService, "request", new=AsyncMock(return_value=MESSAGE)
            ) as send,
        ):
            response = client.post(
                "/auth/register",
                json={"email": account.email, "password": "Password-123"},
            )
            assert response.status_code == 201
            assert response.json()["email_verified"] is False
            assert send.await_args.kwargs == {"automatic": True}
        app.dependency_overrides.pop(get_current_user)
        assert client.post("/auth/email-verification/request").status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_migration_keeps_existing_users_unverified_and_roundtrips():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255))")
        )
        connection.execute(text("INSERT INTO users VALUES (1, 'old@example.com')"))
        migration = load_migration(
            "e42a31f7c908_email_verification.py",
            Operations(MigrationContext.configure(connection)),
        )
        migration.upgrade()
        assert connection.execute(
            text("SELECT email, email_verified_at FROM users")
        ).one() == ("old@example.com", None)
        assert set(EmailVerificationToken.__table__.columns.keys()) == {
            c["name"]
            for c in inspect(connection).get_columns("email_verification_tokens")
        }
        migration.downgrade()
        assert connection.scalar(text("SELECT email FROM users")) == "old@example.com"
        assert "email_verification_tokens" not in inspect(connection).get_table_names()
    engine.dispose()
