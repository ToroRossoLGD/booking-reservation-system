import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.services.password_reset_service import PasswordResetService


def user():
    return MagicMock(id=12, email="owner@example.com", token_version=3)


def reset_token(**overrides):
    values = {
        "id": 5,
        "user_id": 12,
        "token_hash": hashlib.sha256(
            b"valid-reset-token-value-long-enough"
        ).hexdigest(),
        "created_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(minutes=20),
        "consumed_at": None,
    }
    values.update(overrides)
    return MagicMock(**values)


@pytest.mark.asyncio
async def test_request_stores_only_hash_and_emails_raw_token():
    service = PasswordResetService(AsyncMock())
    service.user_repository.get_by_email = AsyncMock(return_value=user())

    async def persist(created, now):
        created.id = 5
        return created

    service.repository.replace_active_token = AsyncMock(side_effect=persist)
    tasks = BackgroundTasks()

    result = await service.request_reset("OWNER@example.com", tasks)

    stored = service.repository.replace_active_token.await_args.args[0]
    emailed_token = tasks.tasks[0].args[2].split("password: ")[1].split("\n")[0]
    assert stored.token_hash == hashlib.sha256(emailed_token.encode()).hexdigest()
    assert stored.token_hash != emailed_token
    assert "If an account exists" in result["message"]
    service.user_repository.get_by_email.assert_awaited_once_with("owner@example.com")


@pytest.mark.asyncio
async def test_unknown_email_gets_same_response_without_email_or_token():
    service = PasswordResetService(AsyncMock())
    service.user_repository.get_by_email = AsyncMock(return_value=None)
    service.repository.replace_active_token = AsyncMock()
    tasks = BackgroundTasks()

    result = await service.request_reset("missing@example.com", tasks)

    assert result["message"] == service.GENERIC_REQUEST_MESSAGE
    assert tasks.tasks == []
    service.repository.replace_active_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_token_changes_password_atomically():
    service = PasswordResetService(AsyncMock())
    service.repository.get_by_hash = AsyncMock(return_value=reset_token())
    service.repository.consume_and_change_password = AsyncMock(return_value=True)

    with patch(
        "app.services.password_reset_service.hash_password",
        return_value="new-password-hash",
    ):
        result = await service.confirm_reset(
            "valid-reset-token-value-long-enough", "NewPassword123"
        )

    call = service.repository.consume_and_change_password.await_args.kwargs
    assert call["hashed_password"] == "new-password-hash"
    assert (
        call["token_hash"]
        == hashlib.sha256(b"valid-reset-token-value-long-enough").hexdigest()
    )
    assert result["message"] == "Password has been reset successfully."


@pytest.mark.asyncio
async def test_unknown_reset_token_is_rejected():
    service = PasswordResetService(AsyncMock())
    service.repository.get_by_hash = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.confirm_reset("unknown-token", "NewPassword123")

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_consumed_reset_token_cannot_be_replayed():
    service = PasswordResetService(AsyncMock())
    service.repository.get_by_hash = AsyncMock(
        return_value=reset_token(consumed_at=datetime.now(UTC))
    )
    service.repository.consume_and_change_password = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.confirm_reset("used-token", "NewPassword123")

    assert error.value.status_code == 409
    service.repository.consume_and_change_password.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_reset_token_is_gone():
    service = PasswordResetService(AsyncMock())
    service.repository.get_by_hash = AsyncMock(
        return_value=reset_token(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    service.repository.consume_and_change_password = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.confirm_reset("expired-token", "NewPassword123")

    assert error.value.status_code == 410
    service.repository.consume_and_change_password.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_consumer_loser_gets_conflict():
    service = PasswordResetService(AsyncMock())
    service.repository.get_by_hash = AsyncMock(return_value=reset_token())
    service.repository.consume_and_change_password = AsyncMock(return_value=False)

    with patch(
        "app.services.password_reset_service.hash_password",
        return_value="new-password-hash",
    ):
        with pytest.raises(HTTPException) as error:
            await service.confirm_reset("racing-token", "NewPassword123")

    assert error.value.status_code == 409
