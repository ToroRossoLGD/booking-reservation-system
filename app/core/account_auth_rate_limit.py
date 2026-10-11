"""Auth target budgets shared across client IPs and application replicas."""

import hashlib
import hmac
import json

from fastapi import HTTPException

from app.core.auth_rate_limit import enforce_budget
from app.core.config import settings

POLICIES = {
    "login": (30, 900),
    "reset-request": (3, 900),
    "verification-request": (3, 900),
}


def target_key(action: str, identity: str) -> str:
    # Conservative grouping, not a change to account lookup semantics. No raw
    # email, user ID, credentials or tokens are stored in the Redis key.
    normalized = identity.strip().casefold()
    digest = hmac.new(
        settings.JWT_SECRET.encode(),
        f"auth-target:{normalized}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"bookica:auth-target:v1:{action}:{digest}"


async def limit_auth_target(action: str, identity: str) -> None:
    if settings.APP_ENV != "production" and not settings.AUTH_RATE_LIMIT_ENABLED:
        return
    limit, seconds = POLICIES[action]
    response = await enforce_budget(target_key(action, identity), limit, seconds)
    if response is not None:
        raise HTTPException(
            response.status_code,
            json.loads(response.body)["detail"],
            headers={
                name: response.headers[name]
                for name in ("Retry-After", "Cache-Control")
            },
        )
