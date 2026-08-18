import json
from datetime import datetime
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)


def build_available_slots_cache_key(
    resource_id: int,
    selected_date,
    slot_minutes: int,
) -> str:
    # Keep the version suffix inside the existing invalidation pattern. Version 2
    # stores remaining_capacity in addition to the old boolean availability flag.
    return f"available_slots:{resource_id}:{selected_date}:{slot_minutes}:v2"


async def get_cache(
    key: str,
) -> Any | None:
    value = await redis_client.get(key)

    if value is None:
        return None

    return json.loads(value)


async def set_cache(
    key: str,
    value: Any,
    ttl_seconds: int | None = None,
) -> None:
    if ttl_seconds is None:
        ttl_seconds = settings.CACHE_TTL_SECONDS

    await redis_client.set(
        key,
        json.dumps(value, default=_json_serializer),
        ex=ttl_seconds,
    )


async def delete_cache(
    key: str,
) -> None:
    await redis_client.delete(key)


async def delete_available_slots_cache_for_resource(
    resource_id: int,
) -> None:
    pattern = f"available_slots:{resource_id}:*"

    async for key in redis_client.scan_iter(match=pattern):
        await redis_client.delete(key)


def _json_serializer(value):
    if isinstance(value, datetime):
        return value.isoformat()

    raise TypeError(f"Type {type(value)} is not JSON serializable")
