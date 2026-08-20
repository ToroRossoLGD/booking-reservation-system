import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.api_key import APIKey
from app.models.user import User
from app.repositories.api_key_repository import APIKeyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.api_key import APIKeyCreate


class APIKeyService:
    def __init__(self, db: AsyncSession):
        self.repository = APIKeyRepository(db)
        self.user_repository = UserRepository(db)

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    async def create(self, data: APIKeyCreate, current_user: User) -> dict:
        now = datetime.now(UTC)
        secret = secrets.token_urlsafe(32)
        prefix = secrets.token_hex(4)
        raw_key = f"brs_{prefix}_{secret}"
        api_key = APIKey(
            user_id=current_user.id,
            name=data.name,
            key_prefix=f"brs_{prefix}",
            key_hash=self._hash_key(raw_key),
            created_at=now,
            expires_at=(
                now + timedelta(days=data.expires_in_days)
                if data.expires_in_days is not None
                else None
            ),
        )
        api_key = await self.repository.create_if_below_limit(
            api_key, now, settings.MAX_ACTIVE_API_KEYS
        )
        if api_key is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A user can have at most {settings.MAX_ACTIVE_API_KEYS} "
                    "active API keys"
                ),
            )
        return {**api_key.__dict__, "key": raw_key}

    async def list(self, current_user: User) -> list[APIKey]:
        return await self.repository.list_for_user(current_user.id)

    async def revoke(self, api_key_id: int, current_user: User) -> APIKey:
        api_key = await self.repository.get_for_user(api_key_id, current_user.id)
        if api_key is None:
            raise HTTPException(status_code=404, detail="API key not found")
        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(UTC)
            api_key = await self.repository.update(api_key)
        return api_key

    async def authenticate(self, raw_key: str) -> User | None:
        now = datetime.now(UTC)
        user_id = await self.repository.record_use_if_valid(
            self._hash_key(raw_key), now
        )
        if user_id is None:
            return None
        return await self.user_repository.get_by_id(user_id)
