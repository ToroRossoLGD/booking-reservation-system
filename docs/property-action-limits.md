# Property action limits

Property inquiries, messages, reports and photo uploads now use shared Redis budgets by both client IP and authenticated account. They reuse the atomic expiring counters and trusted proxy boundary from [auth request limits](auth-rate-limits.md). No database migration is required.

| Action | Per account | Per IP | Window |
| --- | ---: | ---: | ---: |
| New rental or purchase inquiry | 10 | 30 | 15 minutes |
| Chat message, owner reply or viewing proposal | 30 | 120 | 60 seconds |
| New property report | 5 | 30 | 15 minutes |
| Property photo upload | 20 | 60 | 15 minutes |

Rental and sale actions share their respective inquiry/message budgets. Keys do not contain listing IDs, inquiry IDs or credential IDs: switching listings, conversations, bearer sessions or API keys does not reset an account budget. Separate accounts have separate account budgets, while users behind the same NAT share the IP budget. IPv6 addresses within one /64 share an IP budget. Admin and owner roles have no bypass.

Account identity comes from the existing authenticated-user dependency, including token-version/API-key validation. The limiter does not trust a user-ID header or decode an unvalidated JWT. Redis keys contain keyed hashes rather than raw addresses or account IDs. The existing authorization, verified-email, upload-size, media quota and inquiry-state rules still apply after a request passes these budgets.

## Protected routes and order

The following POST routes check an IP budget before request-body parsing, including multipart processing, then the authenticated account budget before business writes:

- `/properties/{id}/rental-inquiries` and `/properties/{id}/sale-inquiries`.
- `/rental-inquiries/{id}/messages` and `/sale-inquiries/{id}/messages`.
- `/properties/{id}/reports`.
- `/owner/properties/{id}/photos`.

For `PATCH /rental-inquiries/{id}` and `PATCH /sale-inquiries/{id}`, the validated `reply` and `propose` actions consume the same IP/account message budgets before calling the service. This prevents using the owner reply/viewing form to bypass the chat limit. These PATCH bodies must be parsed to identify the action; proxy body-size limits still apply.

Reading conversations, marking messages read, browsing, listing photos, photo deletion/reordering, closing/withdrawing inquiries and accepting/declining a viewing do not consume these budgets. The limiter does not block those actions when Redis is unavailable; their own service dependencies can still fail independently. Nightly booking, legacy hourly APIs and unrelated upload endpoints are outside this feature.

## Responses and retries

`429` includes `Retry-After` and `Cache-Control: no-store`; allowed browser origins can read the retry header, and responses retain their request ID. The UI shows the wait and retains inquiry/message/report text or queued photos. It preserves the existing body request ID for an unchanged retry, so idempotency protections remain effective. It does not automatically retry. A retry before expiry is still rejected.

The temporary report throttle is distinguished from the existing maximum-open-report quota: only the temporary limit has `Retry-After`. Waiting does not resolve the separate open-report quota.

Attempts, including explicit retries and later business validation failures, consume budget. IP and account checks are sequential: an account rejection still consumes an IP attempt. Unauthenticated requests never select an account bucket. The IP layer also counts malformed bodies, while the account check runs after authentication and body parsing. Counters expire from their first request; rejected requests do not extend the window. These are fixed windows, not sliding windows.

Redis failure returns a generic `503` with a 30-second suggested retry for protected writes. There is no in-memory fallback or fail-open path. Logs say only `Property rate limiter unavailable`. Account and IP counters are shared across workers and survive API restarts; Redis data loss or JWT-secret rotation can reset them. No email addresses, messages, file contents or tokens enter limiter logs/keys.

## Enablement and remaining acceptance

Production, including isolated demos, always enforces these limits. Development/test may opt in with `PROPERTY_RATE_LIMIT_ENABLED=true`; the default there is false. Demo's existing multipart-upload ban still runs before the limiter and remains in force. The auth-development flag is independent.

Use the existing [trusted proxy setup](auth-rate-limits.md#client-address-and-tls-proxy-boundary). Before hosting, verify separate real clients get the expected IP budgets and that forged forwarding headers cannot alter them. Tune the checked-in policy values using observed legitimate traffic and the expected NAT topology, with tests updated alongside any change.

Automated coverage verifies every protected route, shared rental/sale budgets, bearer/API-key account identity, retained business rules, blocking before multipart parsing, 429/CORS metadata, Redis failure and unaffected management actions. Existing real-Redis concurrency/expiry tests cover the shared counter implementation. Production CI exhausts real account and IP budgets through Nginx, changes listing IDs and forwarding headers, recreates services and stops Redis. Component tests cover retained inputs/files; desktop/mobile browser tests exercise a throttled conversation and explicit retry.

This implements another portion of P1 abuse hardening. Distributed/multi-account abuse, account-targeted auth defenses, OAuth/legacy endpoint limits, session/token storage review, security headers, operational monitoring and real hosted proxy acceptance remain open. The parent roadmap item stays unchecked.
