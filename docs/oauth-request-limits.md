# Google OAuth request budgets

Production now protects both public Google OAuth GET endpoints before generating
state or attempting a provider token exchange. They use the existing shared Redis
IP limiter, with independent windows:

| Endpoint | Attempts | Window |
| --- | ---: | ---: |
| `/auth/google/login` | 10 | 60 seconds |
| `/auth/google/callback` | 20 | 60 seconds |

Query parameters, state/code values and trailing slashes do not create new buckets.
The `/api` proxy prefix is normalized. As with the POST auth budgets, only the
trusted ASGI client address is used; incoming forwarding headers are not parsed
by the application. IPv6 /64 grouping, HMAC keys, atomic expiry, restart persistence
and mandatory production enforcement remain unchanged. OAuth state, codes and
cookies are never used as Redis keys. GET provider discovery and existing-session
reads remain outside these budgets.

All attempts count, including canceled flows and callbacks missing state. The
start and callback budgets are separate so initiating a login does not consume
the callback allowance. These limits supplement existing state/nonce/PKCE checks;
they do not replace them or impose an unauthenticated email/account lockout.

## Browser and API responses

An exhausted budget returns 429 and `Retry-After`; Redis failure returns 503 with
a 30-second suggested wait. Both are `Cache-Control: no-store`. Requests accepting
`text/html` get a Serbian page with a link back to the configured frontend account
page. It contains no external resources, scripts, copied query parameters or
automatic retry. A restrictive CSP blocks embedding and resource loading, and
the return link uses `rel=noreferrer` to keep callback query data out of navigation
referrers. Other clients retain the existing JSON error format.

Both response formats expire the OAuth state cookie on `/auth/google`; production
nginx rewrites that path to `/api/auth/google`. A rejected callback must restart
the flow rather than retry its old code. Bearer sessions and API keys are untouched.
The error page does not remove the callback URL from browser history, so do not
share callback URLs or screenshots containing their query strings.

## Validation and remaining work

Tests cover proxy/trailing-slash normalization, independent policies, allowed
redirects, blocking before provider calls, redacted 429/503 browser pages, JSON/CORS
metadata and method handling. Production Chromium exhausts the real callback
budget through nginx without contacting Google, checks the mobile page and cookie
path, and verifies the return link sends no Referer. Existing Redis tests cover
concurrent atomic counters, expiry and failure behavior.

This completes the OAuth endpoint-budget portion of P1. Real Google provider
acceptance on private HTTPS staging, trusted client-IP verification, legacy route
budgets, distributed/multi-account abuse and operational tuning remain open.
Clients behind one NAT share these budgets. No migration or new setting is needed;
development can opt in with `AUTH_RATE_LIMIT_ENABLED`.
