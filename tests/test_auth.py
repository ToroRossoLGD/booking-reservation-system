from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.main import app
from app.services.auth_service import AuthService

client = TestClient(app)


def test_login_with_invalid_credentials_returns_401():
    response = client.post(
        "/auth/login",
        data={
            "username": "notfound@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_google_authorization_uses_state_nonce_and_pkce(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/auth/google/callback",
    )

    authorization_url, state_token = AuthService.create_google_authorization()
    query = parse_qs(urlparse(authorization_url).query)

    assert query["client_id"] == ["google-client"]
    assert query["scope"] == ["openid email profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"]
    assert query["nonce"]
    assert AuthService._decode_google_state(state_token, query["state"][0])


@pytest.mark.asyncio
async def test_google_login_creates_customer_and_returns_access_token(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")
    service = AuthService(AsyncMock())
    service.user_repository.get_by_google_sub = AsyncMock(return_value=None)
    service.user_repository.get_by_email = AsyncMock(return_value=None)
    created_user = MagicMock(id=42, token_version=0)
    service.user_repository.create = AsyncMock(return_value=created_user)
    token_response = MagicMock()
    token_response.json.return_value = {
        "id_token": "google-id-token",
        "access_token": "google-access-token",
    }
    certs_response = MagicMock()
    certs_response.json.return_value = {"keys": [{"kid": "key-1"}]}
    http_client = AsyncMock()
    http_client.post.return_value = token_response
    http_client.get.return_value = certs_response
    http_context = AsyncMock()
    http_context.__aenter__.return_value = http_client

    with (
        patch.object(
            AuthService,
            "_decode_google_state",
            return_value={"nonce": "nonce-1", "verifier": "verifier-1"},
        ),
        patch("app.services.auth_service.httpx.AsyncClient", return_value=http_context),
        patch(
            "app.services.auth_service.jwt.get_unverified_header",
            return_value={"kid": "key-1"},
        ),
        patch(
            "app.services.auth_service.jwt.decode",
            return_value={
                "sub": "google-user-1",
                "iss": "https://accounts.google.com",
                "email": "Person@Example.com",
                "email_verified": True,
                "nonce": "nonce-1",
            },
        ) as decode_id_token,
    ):
        token = await service.login_with_google("code-1", "state-1", "cookie-1")

    assert token
    created = service.user_repository.create.await_args.args[0]
    assert created.email == "person@example.com"
    assert created.google_sub == "google-user-1"
    assert created.role == "customer"
    assert decode_id_token.call_args.kwargs["access_token"] == "google-access-token"


@pytest.mark.asyncio
async def test_password_reset_invalidates_previously_issued_access_tokens():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = MagicMock(id=7, token_version=2)
    db.execute.return_value = result
    old_token = create_access_token(subject=7, token_version=1)

    with pytest.raises(HTTPException) as error:
        await get_current_user(token=old_token, api_key=None, db=db)

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_current_token_version_remains_valid():
    db = AsyncMock()
    current_user = MagicMock(id=7, token_version=2)
    result = MagicMock()
    result.scalar_one_or_none.return_value = current_user
    db.execute.return_value = result
    current_token = create_access_token(subject=7, token_version=2)

    authenticated = await get_current_user(token=current_token, api_key=None, db=db)

    assert authenticated is current_user


@pytest.mark.asyncio
async def test_api_key_authentication_uses_same_current_user_path():
    authenticated_user = MagicMock(id=8, role="owner")
    with patch(
        "app.core.dependencies.APIKeyService.authenticate",
        new=AsyncMock(return_value=authenticated_user),
    ) as authenticate:
        result = await get_current_user(
            token=None,
            api_key="brs_12345678_secret",
            db=AsyncMock(),
        )

    assert result is authenticated_user
    authenticate.assert_awaited_once_with("brs_12345678_secret")


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401():
    with patch(
        "app.core.dependencies.APIKeyService.authenticate",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as error:
            await get_current_user(
                token=None,
                api_key="invalid-key",
                db=AsyncMock(),
            )

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_bearer_token_and_api_key_returns_401():
    with pytest.raises(HTTPException) as error:
        await get_current_user(token=None, api_key=None, db=AsyncMock())

    assert error.value.status_code == 401
