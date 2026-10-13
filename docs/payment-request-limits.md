# Legacy payment request budgets

The existing hourly-reservation payment endpoints now use the shared Redis
write limiter. This P1 protection does not add online payments for nightly stays;
that remains a separate P2 feature.

| Operation | Per IP | Per authenticated account | Window |
| --- | ---: | ---: | --- |
| `POST /payments/reservations/{id}/pay` | 30 | 5 | 15 minutes |
| `POST /payments/reservations/{id}/checkout` | Shares pay budget | Shares pay budget | 15 minutes |

Both routes share counters across reservation IDs. Authenticated user IDs bind
account budgets across IPs, bearer tokens and API keys. Administrators have no
exemption. Limits count attempts reaching each check, including validation and
ownership failures and repeated checkout attempts. Tune the initial limits
against actual workload before launch.

The trusted ASGI client address is checked before authentication; the account
budget is checked before either payment service runs. Exhaustion returns 429
with `Retry-After`, `Cache-Control: no-store` and a request ID. Redis failure
returns redacted 503 with a 30-second suggested retry. No payment or checkout
service is invoked for rejected requests. Existing ownership, reservation-state,
Stripe configuration and payment checks still apply.

Payment reads and `/payments/stripe/webhook` do not consume these budgets.
Webhook signature validation and event handling remain unchanged: customer
throttling must not prevent provider notifications from reaching validation.
Reservation cancellation is also outside this budget. These exclusions do not
guarantee availability when unrelated services fail.

Production always enforces the limits; development/test opts in with
`AUTH_RATE_LIMIT_ENABLED`. The shared atomic Redis implementation and HMAC key
identities are reused; existing limiter keys are unchanged. Shared NATs share IP
allowances, fixed windows permit boundary bursts, and Redis data loss or
JWT-secret rotation can reset counters. Do not flush shared Redis to unblock a
user. No migration or new environment variable is required.

Tests cover shared counters, normalized paths, account isolation, retries,
fail-closed behavior without payment side effects, ownership rejection, payment
reads and webhook access during limiter outages. Production-profile CI adds
exhaustion and API/Redis recreation checks using invalid reservation IDs, so it
cannot create payments or contact Stripe. Local unit tests do not replace this
real-stack acceptance or actual HTTPS staging/client-IP validation.

Legacy media uploads now have [request budgets](media-request-limits.md). Other
legacy endpoint protection, broader abuse defenses and hosted acceptance remain
open P1 work.
