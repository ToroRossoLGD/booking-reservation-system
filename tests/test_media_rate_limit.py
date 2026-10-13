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
from app.services.media_storage_service import MediaStorageService

PATHS = ["/venues/1/media", "/resources/2/media"]


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    counter = AsyncMock(return_value=[1, 60000])
    monkeypatch.setattr(auth_rate_limit.redis_client, "eval", counter)
    user = User(id=42, email="media@example.com", role="owner", token_version=0)

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
async def test_shared_ip_budget_across_parents_and_normalized_paths(setup):
    counter, _ = setup
    for path in PATHS + ["/venues/999/media"]:
        for candidate, root in [(path, ""), (path + "/", ""), ("/api" + path, "/api")]:
            assert (
                await limits.enforce_legacy_write_ip_limit(request(candidate, root))
                is None
            )
    assert all(call.args == counter.await_args.args for call in counter.await_args_list)


@pytest.mark.asyncio
async def test_account_budget_spans_parents_and_ips_but_not_users(setup):
    counter, user = setup
    await limits.limit_legacy_write_account(request(PATHS[0]), user)
    await limits.limit_legacy_write_account(request(PATHS[1], host="203.0.113.1"), user)
    assert counter.await_args_list[0].args == counter.await_args_list[1].args
    key = counter.await_args.args[2]
    assert counter.await_args.args[3:] == (20, 900000)
    user.id = 43
    await limits.limit_legacy_write_account(request(PATHS[0]), user)
    assert counter.await_args.args[2] != key


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("stage", ["ip", "account"])
@pytest.mark.parametrize("unavailable", [False, True])
def test_rejected_upload_never_reaches_storage(setup, path, stage, unavailable):
    counter, _ = setup
    rejection = (
        ConnectionError("private Redis configuration") if unavailable else [0, 2501]
    )
    counter.side_effect = [rejection] if stage == "ip" else [[1, 60000], rejection]
    with patch.object(MediaStorageService, "upload", new=AsyncMock()) as upload:
        response = TestClient(app).post(
            path,
            files={"file": ("test.png", b"image", "image/png")},
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == (503 if unavailable else 429)
        assert response.headers["Retry-After"] == ("30" if unavailable else "3")
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Request-ID"]
        assert (
            response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        )
        assert "private" not in response.text
        upload.assert_not_awaited()


@pytest.mark.parametrize("path", PATHS)
def test_ip_rejection_precedes_multipart_parsing_and_auth(setup, path):
    counter, _ = setup
    app.dependency_overrides.pop(get_current_user)
    counter.return_value = [0, 60000]
    response = TestClient(app).post(
        path, content=b"broken", headers={"Content-Type": "multipart/form-data"}
    )
    assert response.status_code == 429
    counter.assert_awaited_once()


@pytest.mark.parametrize("path", PATHS)
def test_empty_smoke_request_consumes_budgets_without_storage(setup, path):
    counter, _ = setup
    with patch.object(MediaStorageService, "upload", new=AsyncMock()) as upload:
        assert TestClient(app).post(path, json={}).status_code == 422
        assert counter.await_count == 2
        upload.assert_not_awaited()


@pytest.mark.parametrize("path", PATHS)
def test_ownership_check_remains_with_available_budget(setup, path):
    with patch.object(
        MediaStorageService,
        "upload",
        new=AsyncMock(side_effect=HTTPException(403, "Not your media")),
    ) as upload:
        response = TestClient(app).post(
            path, files={"file": ("test.png", b"image", "image/png")}
        )
        assert response.status_code == 403
        upload.assert_awaited_once()


def test_reads_and_deletion_remain_available_during_outage(setup):
    counter, _ = setup
    counter.side_effect = ConnectionError("offline")
    with (
        patch.object(
            MediaStorageService, "list", new=AsyncMock(return_value=[])
        ) as listing,
        patch.object(
            MediaStorageService,
            "delete",
            new=AsyncMock(side_effect=HTTPException(404, "Missing media")),
        ) as delete,
    ):
        client = TestClient(app)
        for path in PATHS:
            assert client.get(path).status_code == 200
        assert listing.await_count == 2
        assert client.delete("/media/999").status_code == 404
        delete.assert_awaited_once()
    counter.assert_not_awaited()


@pytest.mark.parametrize("path", PATHS)
def test_production_cannot_disable_limits(setup, monkeypatch, path):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", False)
    assert limits.policy_for(request(path)) is not None
