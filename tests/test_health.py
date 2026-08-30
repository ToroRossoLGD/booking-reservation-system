from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
