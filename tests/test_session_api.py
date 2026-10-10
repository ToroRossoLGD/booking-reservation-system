from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services.session_service import SessionService


def test_logout_all_requires_authentication():
    async def database():
        yield AsyncMock()

    app.dependency_overrides[get_db] = database
    try:
        assert TestClient(app).post("/auth/logout-all").status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_logout_all_uses_authenticated_account_and_returns_empty_no_store(monkeypatch):
    user = User(id=1, role="customer", token_version=0)
    revoke = AsyncMock()
    monkeypatch.setattr(SessionService, "revoke_all", revoke)

    async def database():
        yield AsyncMock()

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = TestClient(app).post("/auth/logout-all", json={"user_id": 2})
        assert response.status_code == 204
        assert response.content == b""
        assert response.headers["cache-control"] == "no-store"
        revoke.assert_awaited_once_with(user)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
