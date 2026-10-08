from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.demo import validate_target
from app.demo_assets import illustration
from app.main import app
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.media_storage_service import MediaStorageService
from app.services.property_photo_service import PropertyPhotoService
from app.services.stripe_service import StripeService
from app.services.webhook_service import WebhookService


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)


def test_demo_does_not_send_email_even_with_smtp_configured(demo, monkeypatch):
    smtp = MagicMock(side_effect=AssertionError("network reached"))
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP", smtp)
    EmailService().send_email("person@example.com", "private", "private body")
    smtp.assert_not_called()


def test_demo_refuses_stripe_and_oauth_even_with_credentials(demo, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_live_configured")
    monkeypatch.setattr(settings, "STRIPE_ALLOW_LIVE_MODE", True)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "configured")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "configured")
    with pytest.raises(HTTPException, match="Payments"):
        StripeService._configure()
    assert not AuthService.google_oauth_configured()
    with pytest.raises(HTTPException):
        AuthService.create_google_authorization()


@pytest.mark.asyncio
async def test_demo_does_not_access_webhook_network_or_queue(demo):
    service = WebhookService(AsyncMock())
    service.repository.get_due_deliveries = AsyncMock(side_effect=AssertionError())
    assert (await service.deliver_due())["processed"] == 0
    with pytest.raises(HTTPException):
        await service.create(1, None, None)


@pytest.mark.asyncio
async def test_demo_blocks_registration_and_uploads_before_reading_files(demo):
    with pytest.raises(HTTPException):
        await AuthService(AsyncMock()).register(None)
    file = MagicMock()
    file.read = AsyncMock(side_effect=AssertionError())
    with pytest.raises(HTTPException):
        await PropertyPhotoService(AsyncMock()).upload(1, file, None, None)
    file.read.assert_not_called()
    with pytest.raises(HTTPException):
        MediaStorageService(AsyncMock())._client()


def test_demo_public_metadata_and_multipart_guard(demo):
    client = TestClient(app)
    response = client.get("/runtime-config")
    assert response.json() == {"demo": True}
    assert response.headers["cache-control"] == "no-store"
    assert (
        client.post(
            "/owner/properties/1/photos", files={"file": ("x.jpg", b"x")}
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "mode,database,action,apply,confirmation",
    [
        (False, "bookica_demo", "seed", True, None),
        (True, "bookica", "reset", True, "bookica"),
        (True, "bookica_demo", "reset", True, None),
        (True, "bookica_demo", "reset", True, "other_demo"),
    ],
)
def test_reset_and_seed_guards(
    monkeypatch, mode, database, action, apply, confirmation
):
    monkeypatch.setattr(settings, "DEMO_MODE", mode)
    with pytest.raises(ValueError):
        validate_target(database, action, apply, confirmation)


def test_reset_preview_and_explicit_confirmation(demo):
    validate_target("bookica_demo", "reset", False, None)
    validate_target("bookica_demo", "reset", True, "bookica_demo")


def test_demo_startup_rejects_normal_database():
    values = settings.model_dump()
    values.update(
        DEMO_MODE=True,
        POSTGRES_DB="customer_data",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/customer_data",
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_bundled_illustrations_have_no_external_references():
    for key in ("demo/river", "demo/garden", "demo/home"):
        asset = illustration(key)
        assert asset.startswith(b"<svg")
        assert b"href" not in asset and b"script" not in asset
    with pytest.raises(HTTPException):
        illustration("../../.env")
