from fastapi.testclient import TestClient

from app.main import app


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