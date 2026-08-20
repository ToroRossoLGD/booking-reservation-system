from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.core.security import create_access_token
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


@pytest.mark.asyncio
async def test_password_reset_invalidates_previously_issued_access_tokens():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = MagicMock(id=7, token_version=2)
    db.execute.return_value = result
    old_token = create_access_token(subject=7, token_version=1)

    with pytest.raises(HTTPException) as error:
        await get_current_user(token=old_token, db=db)

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_current_token_version_remains_valid():
    db = AsyncMock()
    current_user = MagicMock(id=7, token_version=2)
    result = MagicMock()
    result.scalar_one_or_none.return_value = current_user
    db.execute.return_value = result
    current_token = create_access_token(subject=7, token_version=2)

    authenticated = await get_current_user(token=current_token, db=db)

    assert authenticated is current_user
