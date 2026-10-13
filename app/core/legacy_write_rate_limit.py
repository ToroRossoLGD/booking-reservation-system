"""Shared budgets for legacy integration, support, reservation and payment writes."""

import hashlib
import hmac
import json
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


WEBHOOK_WRITE = Policy("webhook-write", 30, 10, 900)
SUPPORT_MESSAGE = Policy("support-message", 120, 30, 60)
RESERVATION_WRITE = Policy("reservation-write", 60, 10, 900)
POLICIES = (
    (
        "POST",
        re.compile(r"/payments/reservations/[^/]+/(?:pay|checkout)"),
        Policy("payment-write", 30, 5, 900),
    ),
    ("POST", re.compile(r"/reservations"), RESERVATION_WRITE),
    ("PATCH", re.compile(r"/reservations/[^/]+/reschedule"), RESERVATION_WRITE),
    (
        "POST",
        re.compile(r"/reservations/recurring"),
        Policy("reservation-recurring", 10, 2, 900),
    ),
    ("POST", re.compile(r"/support/tickets"), Policy("support-ticket", 30, 5, 900)),
    (
        "POST",
        re.compile(r"/support/(?:admin/)?tickets/[^/]+/messages"),
        SUPPORT_MESSAGE,
    ),
    ("POST", re.compile(r"/auth/api-keys"), Policy("key-create", 30, 5, 900)),
    ("POST", re.compile(r"/venues/[^/]+/webhooks"), WEBHOOK_WRITE),
    ("PUT", re.compile(r"/venues/[^/]+/webhooks/[^/]+"), WEBHOOK_WRITE),
    (
        "POST",
        re.compile(r"/venues/[^/]+/webhooks/deliveries/[^/]+/retry"),
        Policy("webhook-retry", 60, 10, 60),
    ),
)


def policy_for(request: Request) -> Policy | None:
    if settings.APP_ENV != "production" and not settings.AUTH_RATE_LIMIT_ENABLED:
        return None
    path = request.scope["path"]
    root = request.scope.get("root_path", "")
    if root and path.startswith(root + "/"):
        path = path[len(root) :]
    for method, pattern, policy in POLICIES:
        if request.method == method and pattern.fullmatch(path.rstrip("/")):
            return policy
    return None


def account_key(action: str, user_id: int) -> str:
    # Preserve the existing namespace so this refactor does not reset live
    # integration counters. New support actions have distinct budget keys.
    digest = hmac.new(
        settings.JWT_SECRET.encode(),
        f"integration-account:{user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"bookica:integration-limit:v1:account:{action}:{digest}"


async def enforce_legacy_write_ip_limit(request: Request):
    policy = policy_for(request)
    if policy is None:
        return None
    host = request.client.host if request.client else "unknown"
    return await enforce_budget(
        bucket_key(f"integration-{policy.action}", host),
        policy.ip_limit,
        policy.seconds,
        legacy_action=True,
    )


async def limit_legacy_write_account(
    request: Request, user: User = Depends(get_current_user)
) -> None:
    policy = policy_for(request)
    if policy is None:
        return
    response = await enforce_budget(
        account_key(policy.action, user.id),
        policy.account_limit,
        policy.seconds,
        legacy_action=True,
    )
    if response is not None:
        raise HTTPException(
            response.status_code,
            json.loads(response.body)["detail"],
            headers={
                name: response.headers[name]
                for name in ("Retry-After", "Cache-Control")
            },
        )
