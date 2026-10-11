import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.core.account_auth_rate_limit import POLICIES, target_key
from app.core.auth_rate_limit import CONSUME
from app.core.config import settings


@pytest.mark.skipif(not os.getenv("AUTH_TEST_REDIS"), reason="CI provides Redis")
@pytest.mark.asyncio
async def test_shared_atomic_limit_expiry_and_bounded_counter():
    clients = [
        Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
        for _ in range(2)
    ]
    key = f"bookica:auth-limit:test:{uuid4().hex}"
    try:
        results = await asyncio.gather(
            *(clients[i % 2].eval(CONSUME, 1, key, 10, 60000) for i in range(40))
        )
        assert sum(result[0] for result in results) == 10
        assert int(await clients[0].get(key)) == 10
        assert 0 < await clients[0].pttl(key) <= 60000
        await clients[0].pexpire(key, 150)
        assert (await clients[1].eval(CONSUME, 1, key, 10, 60000))[0] == 0
        assert 0 < await clients[0].pttl(key) <= 150
        await asyncio.sleep(0.2)
        assert (await clients[1].eval(CONSUME, 1, key, 10, 60000))[0] == 1
        assert int(await clients[0].get(key)) == 1
        # An old/manual key without a TTL must not become a permanent lockout.
        await clients[0].set(key, 10)
        assert (await clients[1].eval(CONSUME, 1, key, 10, 60000))[0] == 1
        assert await clients[0].pttl(key) > 0
    finally:
        await clients[0].delete(key)
        for client in clients:
            await client.aclose()


@pytest.mark.skipif(not os.getenv("AUTH_TEST_REDIS"), reason="CI provides Redis")
@pytest.mark.asyncio
async def test_target_budget_is_shared_by_replicas_and_normalized_addresses():
    clients = [
        Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
        for _ in range(2)
    ]
    email = f"target-{uuid4().hex}@example.com"
    key = target_key("reset-request", email)
    limit, seconds = POLICIES["reset-request"]
    try:
        results = await asyncio.gather(
            *(
                clients[i % 2].eval(
                    CONSUME,
                    1,
                    target_key(
                        "reset-request", email if i % 2 else f" {email.upper()} "
                    ),
                    limit,
                    seconds * 1000,
                )
                for i in range(16)
            )
        )
        assert sum(result[0] for result in results) == limit
        assert int(await clients[0].get(key)) == limit
        assert 0 < await clients[1].pttl(key) <= seconds * 1000
    finally:
        await clients[0].delete(key)
        for client in clients:
            await client.aclose()
