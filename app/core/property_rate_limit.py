"""Property write budgets, shared across listings, conversations and credentials."""

import hashlib
import hmac
import re
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from starlette.requests import Request

from app.core.auth_rate_limit import bucket_key, enforce_budget
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User


@dataclass(frozen=True)
class Policy:
    action: str
    ip_limit: int
    account_limit: int
    seconds: int


MESSAGE_POLICY = Policy("message", 120, 30, 60)
POLICIES = (
    (
        re.compile(r"/properties/[^/]+/(?:rental|sale)-inquiries"),
        Policy("inquiry", 30, 10, 900),
    ),
    (
        re.compile(r"/(?:rental|sale)-inquiries/[^/]+/messages"),
        MESSAGE_POLICY,
    ),
    (re.compile(r"/properties/[^/]+/reports"), Policy("report", 30, 5, 900)),
    (re.compile(r"/owner/properties/[^/]+/photos"), Policy("photo", 60, 20, 900)),
)


def policy_for(request: Request) -> Policy | None:
    if request.method != "POST":
        return None
    path = request.scope["path"]
    root = request.scope.get("root_path", "")
    if root and path.startswith(root + "/"):
        path = path[len(root) :]
    for pattern, policy in POLICIES:
        if pattern.fullmatch(path.rstrip("/")):
            return policy
    return None


def enabled() -> bool:
    return settings.APP_ENV == "production" or settings.PROPERTY_RATE_LIMIT_ENABLED


def account_key(action: str, user_id: int) -> str:
    digest = hmac.new(
        settings.JWT_SECRET.encode(),
        f"property-account:{user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"bookica:property-limit:v1:account:{action}:{digest}"


async def enforce_property_ip_limit(request: Request):
    policy = policy_for(request) if enabled() else None
    if policy is None:
        return None
    host = request.client.host if request.client else "unknown"
    return await enforce_budget(
        bucket_key(f"property-{policy.action}", host),
        policy.ip_limit,
        policy.seconds,
        property_action=True,
    )


async def limit_property_account(
    request: Request, user: User = Depends(get_current_user)
) -> None:
    policy = policy_for(request) if enabled() else None
    if policy is None:
        return
    # get_current_user validates JWT revocation or API-key state first. Use its
    # persisted user ID, never a caller header, unverified JWT, or key ID.
    response = await enforce_budget(
        account_key(policy.action, user.id),
        policy.account_limit,
        policy.seconds,
        property_action=True,
    )
    raise_if_limited(response)


def raise_if_limited(response) -> None:
    if response is not None:
        raise HTTPException(
            response.status_code,
            "Previše pokušaja. Sačekajte pre novog zahteva."
            if response.status_code == 429
            else "Slanje trenutno nije dostupno. Pokušajte kasnije.",
            headers={
                name: response.headers[name]
                for name in ("Retry-After", "Cache-Control")
            },
        )


async def limit_inquiry_reply(request: Request, user: User) -> None:
    """The owner reply/viewing form shares chat budgets; closing stays available."""
    if not enabled():
        return
    policy = MESSAGE_POLICY
    host = request.client.host if request.client else "unknown"
    for key, limit in (
        (bucket_key(f"property-{policy.action}", host), policy.ip_limit),
        (account_key(policy.action, user.id), policy.account_limit),
    ):
        raise_if_limited(
            await enforce_budget(key, limit, policy.seconds, property_action=True)
        )
