"""Shared, bounded auth request budgets; production never bypasses Redis failures."""

import hashlib
import hmac
import ipaddress
import logging
import math

from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.requests import Request

from app.core.config import settings

logger = logging.getLogger(__name__)
redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    socket_connect_timeout=1,
    socket_timeout=1,
    decode_responses=True,
)

# Count all attempts, including malformed input and successful requests. Each
# action has an independent window starting at its first request from this IP.
POLICIES = {
    "/auth/login": ("login", 10, 60),
    "/auth/register": ("signup", 10, 900),
    "/auth/password-reset/request": ("reset-request", 5, 900),
    "/auth/password-reset/confirm": ("reset-confirm", 20, 60),
    "/auth/email-verification/request": ("verification-request", 5, 900),
    "/auth/email-verification/confirm": ("verification-confirm", 20, 60),
}

# Atomic first increment + TTL avoids immortal counters; rejected requests do
# not extend the window or grow the counter. Redis owns time across replicas.
CONSUME = """
local count = tonumber(redis.call('GET', KEYS[1]) or '0')
local ttl = redis.call('PTTL', KEYS[1])
if ttl < 0 then
  redis.call('SET', KEYS[1], 1, 'PX', ARGV[2])
  return {1, tonumber(ARGV[2])}
end
if count >= tonumber(ARGV[1]) then return {0, ttl} end
redis.call('INCR', KEYS[1])
return {1, ttl}
"""


def bucket_key(action: str, host: str) -> str:
    # Normalize equivalent spellings and mapped IPv4; rotate IPv6 privacy
    # addresses within one /64 into the same budget.
    try:
        address = ipaddress.ip_address(host)
        if isinstance(address, ipaddress.IPv6Address):
            address = address.ipv4_mapped or address
        if isinstance(address, ipaddress.IPv6Address):
            identity = str(ipaddress.ip_network(f"{address}/64", strict=False))
        else:
            identity = str(address)
    except ValueError:
        identity = "unknown"
    digest = hmac.new(
        settings.JWT_SECRET.encode(), identity.encode(), hashlib.sha256
    ).hexdigest()
    return f"bookica:auth-limit:v1:{action}:{digest}"


async def enforce_auth_rate_limit(request: Request) -> JSONResponse | None:
    if settings.APP_ENV != "production" and not settings.AUTH_RATE_LIMIT_ENABLED:
        return None
    if request.method != "POST":
        return None
    path = request.scope["path"]
    root = request.scope.get("root_path", "")
    if root and path.startswith(root + "/"):
        path = path[len(root) :]
    policy = POLICIES.get(path.rstrip("/"))
    if policy is None:
        return None
    action, limit, seconds = policy
    # Never parse X-Forwarded-For here. The trusted server/proxy boundary sets
    # request.client; production Nginx overwrites incoming forwarding headers.
    host = request.client.host if request.client else "unknown"
    return await enforce_budget(bucket_key(action, host), limit, seconds)


async def enforce_budget(
    key: str, limit: int, seconds: int, *, property_action: bool = False
) -> JSONResponse | None:
    """Consume the shared atomic budget without reading or logging request bodies."""
    try:
        allowed, ttl_ms = await redis_client.eval(
            CONSUME, 1, key, limit, seconds * 1000
        )
    except (RedisError, OSError):
        logger.warning(
            "Property rate limiter unavailable"
            if property_action
            else "Auth rate limiter unavailable"
        )
        return JSONResponse(
            {
                "detail": "Slanje trenutno nije dostupno. Pokušajte kasnije."
                if property_action
                else "Prijava i potvrda naloga trenutno nisu dostupne. "
                "Pokušajte kasnije."
            },
            status_code=503,
            headers={"Retry-After": "30", "Cache-Control": "no-store"},
        )
    if allowed:
        return None
    wait = max(1, math.ceil(ttl_ms / 1000))
    return JSONResponse(
        {"detail": "Previše pokušaja. Sačekajte pre novog zahteva."},
        status_code=429,
        headers={"Retry-After": str(wait), "Cache-Control": "no-store"},
    )
