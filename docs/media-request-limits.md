# Legacy media upload budgets

Venue and resource uploads now use the shared legacy Redis write limiter.
Property listing photos already have their own [action limits](property-action-limits.md);
their behavior is unchanged.

| Operation | Per IP | Per authenticated account | Window |
| --- | ---: | ---: | --- |
| `POST /venues/{id}/media` | 60 | 20 | 15 minutes |
| `POST /resources/{id}/media` | Shares venue budget | Shares venue budget | 15 minutes |

Changing parent IDs or switching routes does not reset the budget. Account
counters use authenticated user IDs across IPs, bearer tokens and API keys;
administrators have no exemption. Attempts reaching a check consume its budget,
including missing files and ownership failures. Initial limits require workload
tuning before launch.

IP checks run before application multipart parsing and authentication, using
the trusted ASGI client address. Account checks run after multipart parsing but
before the storage service. They do not prevent request-body buffering at the
proxy or temporary-file spooling during multipart parsing. Existing deployment
body-size restrictions and service file-size/type checks remain necessary;
request counts are not byte or storage-capacity quotas.

Exhaustion returns 429 with `Retry-After`, `Cache-Control: no-store` and a request
ID. Redis failure returns redacted 503 with a 30-second suggested retry. Rejected
requests never invoke the upload service. Existing ownership, demo restrictions,
file validation and storage handling still apply. Production always enforces
these budgets; development/test opts in with `AUTH_RATE_LIMIT_ENABLED`.

Media reads and deletion do not consume these budgets, so limiter failure does
not block cleanup. Their existing access controls and storage dependencies still
apply. Atomic counters and HMAC identities reuse the existing limiter without
changing other action keys. Shared NATs share IP budgets, fixed windows permit
boundary bursts, and Redis data loss or JWT-secret rotation can reset counters.
Do not flush shared Redis to unblock users.

API tests cover shared counters, account isolation, normalized paths, multipart
rejection, retry metadata, fail-closed behavior, ownership rejection and reads/
deletion during outages. Production-profile CI exhausts counters using requests
without files and checks API/Redis recreation, Redis failure and cleanup access.
Those checks do not upload objects or require storage credentials. Local unit
tests do not replace real-stack and private HTTPS staging acceptance.

No migration or new environment variable is required. Other legacy actions,
distributed abuse defenses and hosted client-IP/workload acceptance remain open
P1 work; this does not close the overall abuse-hardening milestone.
