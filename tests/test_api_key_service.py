import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.api_key import APIKeyCreate
from app.services.api_key_service import APIKeyService


def user(user_id=10, role="customer"):
    return MagicMock(id=user_id, role=role, email=f"user{user_id}@example.com")


def api_key(**overrides):
    values = {
        "id": 4,
        "user_id": 10,
        "name": "Reporting integration",
        "key_prefix": "brs_1234abcd",
        "key_hash": hashlib.sha256(b"brs_1234abcd_secret").hexdigest(),
        "created_at": datetime.now(UTC),
        "expires_at": None,
        "last_used_at": None,
        "revoked_at": None,
    }
    values.update(overrides)
    return MagicMock(**values)


@pytest.mark.asyncio
async def test_creation_returns_key_once_but_persists_only_hash():
    service = APIKeyService(AsyncMock())

    async def persist(created, now, maximum):
        created.id = 4
        return created

    service.repository.create_if_below_limit = AsyncMock(side_effect=persist)

    result = await service.create(
        APIKeyCreate(name="Reporting integration", expires_in_days=30), user()
    )

    stored = service.repository.create_if_below_limit.await_args.args[0]
    assert result["key"].startswith(f"{stored.key_prefix}_")
    assert stored.key_hash == hashlib.sha256(result["key"].encode()).hexdigest()
    assert stored.key_hash != result["key"]
    assert stored.expires_at > stored.created_at
    assert stored.expires_at - stored.created_at == timedelta(days=30)


@pytest.mark.asyncio
async def test_non_expiring_key_has_no_expiration():
    service = APIKeyService(AsyncMock())
    service.repository.create_if_below_limit = AsyncMock(
        side_effect=lambda item, now, maximum: item
    )

    result = await service.create(APIKeyCreate(name="CI deployment"), user())

    assert result["expires_at"] is None


@pytest.mark.asyncio
async def test_active_key_limit_is_enforced_before_generation():
    service = APIKeyService(AsyncMock())
    service.repository.create_if_below_limit = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.create(APIKeyCreate(name="One too many"), user())

    assert error.value.status_code == 409
    service.repository.create_if_below_limit.assert_awaited_once()


@pytest.mark.asyncio
async def test_valid_key_authenticates_and_records_last_use():
    service = APIKeyService(AsyncMock())
    authenticated_user = user()
    service.repository.record_use_if_valid = AsyncMock(return_value=10)
    service.user_repository.get_by_id = AsyncMock(return_value=authenticated_user)

    result = await service.authenticate("brs_1234abcd_secret")

    expected_hash = hashlib.sha256(b"brs_1234abcd_secret").hexdigest()
    call = service.repository.record_use_if_valid.await_args.args
    assert call[0] == expected_hash
    assert result is authenticated_user


@pytest.mark.asyncio
async def test_revoked_or_expired_key_cannot_authenticate():
    service = APIKeyService(AsyncMock())
    service.repository.record_use_if_valid = AsyncMock(return_value=None)
    service.user_repository.get_by_id = AsyncMock()

    result = await service.authenticate("brs_1234abcd_secret")

    assert result is None
    service.user_repository.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_key_cannot_authenticate():
    service = APIKeyService(AsyncMock())
    service.repository.record_use_if_valid = AsyncMock(return_value=None)

    assert await service.authenticate("not-a-real-key") is None


@pytest.mark.asyncio
async def test_owner_can_revoke_key_idempotently():
    service = APIKeyService(AsyncMock())
    stored = api_key()
    service.repository.get_for_user = AsyncMock(return_value=stored)
    service.repository.update = AsyncMock(side_effect=lambda item: item)

    result = await service.revoke(4, user())

    assert result.revoked_at is not None
    service.repository.update.assert_awaited_once()

    service.repository.update.reset_mock()
    await service.revoke(4, user())
    service.repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_cannot_revoke_another_users_key():
    service = APIKeyService(AsyncMock())
    service.repository.get_for_user = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.revoke(4, user(99))

    assert error.value.status_code == 404
    service.repository.get_for_user.assert_awaited_once_with(4, 99)


@pytest.mark.asyncio
async def test_list_is_scoped_to_current_user():
    service = APIKeyService(AsyncMock())
    service.repository.list_for_user = AsyncMock(return_value=[api_key()])

    result = await service.list(user(42))

    assert len(result) == 1
    service.repository.list_for_user.assert_awaited_once_with(42)
