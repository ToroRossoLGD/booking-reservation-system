# API-key and webhook write budgets

These limits cover the credential/integration subset of P1 legacy endpoint
hardening. Production always enforces them. Development/test opts in with the
existing `AUTH_RATE_LIMIT_ENABLED` flag; no migration or new setting is required.

| Operations | Per IP | Per authenticated account | Window |
| --- | ---: | ---: | --- |
| Create API key (`POST /auth/api-keys`) | 30 | 5 | 15 minutes |
| Create webhook / update webhook (`POST /venues/{id}/webhooks`, `PUT /venues/{id}/webhooks/{id}`) | 30 | 10 | 15 minutes |
| Manually retry delivery (`POST /venues/{id}/webhooks/deliveries/{id}/retry`) | 60 | 10 | 60 seconds |

Create/update share one webhook-write bucket across every venue/subscription.
Retries share a separate bucket across all venues and deliveries. API keys and
bearer tokens belonging to the same user share account budgets. IP rotation does
not reset the account limit; changing resource IDs does not reset either limit.
Administrators have the same budgets. Existing ownership checks, active-key and
webhook quotas, demo restrictions and delivery state checks still apply.

The IP layer runs before authentication/body parsing, using the trusted ASGI
client address and the existing IPv4/IPv6 normalization. Account identity comes
from validated credentials, never a caller-supplied user ID. The account check
runs before business logic; attempts that pass authentication can count even if
payload validation or authorization later fails. Counters contain HMAC identities,
not raw addresses or key secrets, and use the existing atomic Redis expiry script.

Exhaustion returns 429 with `Retry-After`, `Cache-Control: no-store` and the request
ID. CORS exposes retry metadata to allowed origins. Redis failure returns redacted
503 with a 30-second suggested retry, never a bypass. API clients should wait and
explicitly retry; no frontend integration management screen is introduced here.

## Emergency operations and scope

Reading keys/webhook history, deleting (revoking) keys, deleting (deactivating)
webhooks, secret rotation and account-wide logout do not consume these budgets.
Use the DELETE endpoint for emergency webhook shutdown; a PUT update with
`is_active=false` still belongs to the write budget. Authentication and ownership
remain required. Reads/revocation can still fail for unrelated database or other
service problems.

Incoming provider callbacks and scheduled webhook delivery are not user-triggered
management requests and are not matched by these rules. This does not alter
automatic retries, delivery idempotency, outbound URL validation or guarantee
exactly-once delivery. Reservation/payment/media/support legacy routes and broader
outbound integration review remain separate P1 work.

## Verification and rollout

Tests cover every protected method/path, proxy/trailing-slash normalization,
account/resource isolation, bearer/API-key identity, 429/CORS metadata, Redis
failure, production enforcement and excluded emergency operations. Production
smoke exhausts real account budgets through nginx without creating keys/webhooks
or contacting third parties, checks them after API/Redis recreation, and confirms
that read/revoke/deactivate requests remain available. Shared Redis concurrency
and expiry behavior is exercised by the existing real-Redis CI tests.

Fixed windows can allow bursts at expiry. NAT users share an IP allowance; a
compromised credential can spend its account allowance. API restart preserves
counters, while Redis data loss/restore or JWT-secret rotation may reset them.
Tune budgets on private staging with real client-IP topology and observed usage;
do not flush the shared Redis database to unblock one account. The full P1 abuse
milestone remains open.
