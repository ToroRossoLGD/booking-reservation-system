from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_response_includes_generated_request_id():
    first_response = client.get("/health")
    second_response = client.get("/health")

    first_request_id = first_response.headers["X-Request-ID"]
    assert UUID(first_request_id)
    assert first_request_id != second_response.headers["X-Request-ID"]


def test_response_preserves_valid_request_id():
    request_id = "6cb13cb4-05e6-4e67-bc17-38313c22d25e"

    response = client.get("/health", headers={"X-Request-ID": request_id})

    assert response.headers["X-Request-ID"] == request_id


def test_response_replaces_invalid_request_id():
    response = client.get(
        "/health",
        headers={"X-Request-ID": "not-a-valid-request-id"},
    )

    generated_request_id = response.headers["X-Request-ID"]
    assert UUID(generated_request_id)
    assert generated_request_id != "not-a-valid-request-id"


def test_readiness_check_returns_ready_when_database_responds():
    database = AsyncMock()

    async def override_get_db():
        yield database

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "available"}
    database.execute.assert_awaited_once()


def test_readiness_check_returns_unavailable_when_database_fails():
    database = AsyncMock()
    database.execute.side_effect = SQLAlchemyError("connection failed")

    async def override_get_db():
        yield database

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
    }
