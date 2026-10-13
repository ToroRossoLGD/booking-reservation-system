# Legacy reservation request budgets

P1 now covers admission control for legacy booking creation and rescheduling,
using the existing shared Redis limiter. These endpoints are separate from
property inquiries and nightly-stay flows, whose limits remain unchanged.

| Operation | Per IP | Per authenticated account | Window |
| --- | ---: | ---: | --- |
| `POST /reservations` | 60 | 10 | 15 minutes |
| `PATCH /reservations/{id}/reschedule` | Shares creation budget | Shares creation budget | 15 minutes |
| `POST /reservations/recurring` | 10 | 2 | 15 minutes |

Creation and rescheduling share counters across reservation IDs. Recurring
requests have a separate, stricter budget because one request can create up to
52 occurrences (the existing schema maximum). Limits count requests, not
occurrences: an account can attempt up to 104 recurring occurrences per window.
These initial values need workload tuning before launch.

IP checks precede parsing and authentication and use the trusted ASGI client
address. Account checks use authenticated user IDs, independent of bearer token,
API key, resource or reservation ID. Attempts reaching a check consume its
budget, including invalid requests, authorization failures and idempotent
retries. Retry only after the supplied delay; the reservation service still
handles idempotency, ownership, availability and conflict checks.

Exhaustion returns 429 with `Retry-After`, `Cache-Control: no-store` and a request
ID. Redis failure returns a redacted 503 with a 30-second suggested retry.
Production always enforces budgets; development/test opts in with
`AUTH_RATE_LIMIT_ENABLED`. Existing atomic counters, HMAC identities, proxy
handling and CORS retry-header exposure are reused without changing existing
integration/support keys.

Reads, quotes, individual/series cancellation, confirmation, completion and
administrative maintenance do not consume these budgets. Their authentication
and business rules still apply. Cancellation is not blocked by limiter failure;
this does not guarantee availability if the database or other dependencies fail.

API tests cover all three protected routes, shared counters, path normalization,
retry metadata, production enforcement, fail-closed behavior, ownership and
cancellation during outages. The production-profile CI smoke exercises real
Redis limits, API/Redis recreation and unavailable Redis without creating any
reservations. Local unit tests do not replace that real-stack acceptance.

Shared NATs share IP budgets; fixed windows permit boundary bursts. Redis data
loss or JWT-secret rotation can reset counters. Do not flush shared Redis as a
routine way to unblock a user. Legacy payment initiation now has
[shared request budgets](payment-request-limits.md), as do
[legacy media uploads](media-request-limits.md). Other legacy actions and actual
HTTPS staging acceptance remain separate P1 work. No migration or new environment
variable is required.
