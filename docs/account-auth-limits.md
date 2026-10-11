# Auth budgets shared across IP addresses

Production now combines the existing [IP budgets](auth-rate-limits.md) with a
second, independent target budget. Changing networks or application replicas
does not reset the target's window. Development/test uses the existing
`AUTH_RATE_LIMIT_ENABLED` flag; production always enforces both layers.

| Endpoint | Target | Attempts per 15 minutes |
| --- | --- | ---: |
| `POST /auth/login` | Submitted email | 30 |
| `POST /auth/password-reset/request` | Submitted email | 3 |
| `POST /auth/email-verification/request` | Authenticated user ID | 3 |

IP limits run before request validation. Target limits run after validation,
before account lookup/password verification or token issuance/email scheduling.
Verification resend requires valid authentication first and never trusts an ID
from the request body. Initial signup verification retains its existing issuance
behavior; it is not an authenticated resend.

Login/reset keys use stripped, case-folded input as a conservative grouping rule.
This does not change login or repository lookup semantics and does not remove
email dots or plus suffixes. Different actions have independent budgets. Redis
stores keyed HMAC identities, never plaintext email, user ID, password or token.
All replicas must use the same Redis database and JWT secret.

Every attempt reaching the target check counts, including successful requests,
wrong passwords, unknown accounts and delivery-unavailable responses. Unknown
and existing addresses use the same budget; this limit does not reveal account
existence. A successful login does not reset the counter. Attempts already rejected
by the IP limiter or validation do not reach the target counter.

The shared atomic Redis operation starts a fixed window on the first request.
Rejections do not extend expiry or grow the counter. Exhaustion returns 429,
`Retry-After` and `Cache-Control: no-store`; the existing frontend preserves input
and displays the wait without automatic retry. Redis failure returns redacted 503
instead of bypassing the limit. Existing sessions, logout, and confirmation using
already issued recovery/verification links do not use these target budgets; their
existing authentication and IP controls still apply.

## Limits and acceptance

These are temporary request budgets, not permanent account suspension. An attacker
who knows an address can consume its allowance and temporarily prevent login or
new recovery email. Existing sessions and already issued links remain usable.
Tune these initial values using legitimate traffic and support feedback; do not
clear the whole Redis database to unblock one account. Separate actors targeting
many accounts, password spraying, OAuth, legacy routes and a future adaptive
challenge flow remain separate work. Fixed windows allow bursts around expiry.

Unit/API tests cover exact boundaries, success/failure attempts, multiple IPs,
normalization, action/account isolation, authenticated resend, metadata and Redis
failure. Real Redis CI verifies parallel clients share the normalized target key.
Browser tests verify resend wait feedback and explicit retry. Private HTTPS staging
still needs real-client traffic, provider delivery, Redis/restart acceptance and
capacity tuning before the P1 milestone can close.

API restarts preserve Redis counters. Redis loss/restore and secret rotation can
reset them. No schema migration or new environment variable is required.
