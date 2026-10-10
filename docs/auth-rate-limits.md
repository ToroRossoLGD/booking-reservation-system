# Auth request limits

The API enforces shared Redis budgets before parsing password-login, signup, recovery and verification request bodies. All attempts count, including successful and malformed requests. Limits apply to isolated demos too. Production always enables them; `AUTH_RATE_LIMIT_ENABLED=true` enables the same behavior in development/test. The development default is false so local unit tests do not require Redis; CI separately tests real Redis and the production stack.

| POST endpoint | Attempts | Window |
| --- | ---: | ---: |
| `/auth/login` | 10 | 60 seconds |
| `/auth/register` | 10 | 15 minutes |
| `/auth/password-reset/request` | 5 | 15 minutes |
| `/auth/password-reset/confirm` | 20 | 60 seconds |
| `/auth/email-verification/request` | 5 | 15 minutes |
| `/auth/email-verification/confirm` | 20 | 60 seconds |

Each action has its own budget per IPv4 address or IPv6 /64. Mapped IPv4 addresses share the native IPv4 budget. Redis keys contain an HMAC of the normalized address, never the raw IP, email, password or token. Keys expire after the window, starting at the first request. A single Lua operation increments and assigns expiry atomically across API replicas. Rejected requests neither grow the counter nor extend the wait. This is a fixed window, not a sliding-window or distributed-botnet defense; two bursts around expiry are possible. Users sharing a NAT also share a budget. The existing verification resend cooldown is an additional per-account rule.

An exhausted budget returns `429`, `Retry-After` in whole seconds and `Cache-Control: no-store`. CORS exposes the wait header to allowed origins, and the response retains its request ID. Login, password recovery and email confirmation show a Serbian wait message without automatically retrying or clearing the user's input. A manual retry before expiry still receives 429.

Redis connection/command failures return a generic `503` with a 30-second suggested retry; auth does not silently bypass the limiter. Logs contain only `Auth rate limiter unavailable`. The limiter does not intercept health/readiness, browsing, existing-session reads or unrelated routes. A Redis failure can still affect other existing application functions that already depend on Redis. `/ready` continues to measure the database only; monitoring Redis/503 rates remains part of P1 operations work.

## Client address and TLS proxy boundary

The application uses the client address supplied by the ASGI server, not arbitrary `X-Forwarded-For` or `X-Real-IP` request headers. The production API has no published host port and trusts forwarding from its private proxy network. Keep it private: do not expose the image's Uvicorn listener directly to clients with its existing `--forwarded-allow-ips=*` setting. If deploying outside this Compose profile, configure explicit trusted Uvicorn proxy peers or disable proxy-header processing.

Production Nginx overwrites both forwarded client headers with its resolved `$remote_addr`. The default [trusted proxy file](../deploy/trusted-proxies.conf) trusts **no** incoming peer, so spoofed headers cannot obtain new budgets. The frontend listener is published only on host loopback. Before putting a real TLS proxy in front of it:

1. Identify the actual peer address as seen by Nginx, including Docker NAT or any proxy chain. Restrict access to the listener to that proxy.
2. Place a private file outside the repository, for example `/etc/bookica/trusted-proxies.conf`, containing `set_real_ip_from` for only those exact trusted addresses/CIDRs. Never use `0.0.0.0/0` or `::/0`.
3. Set `BOOKICA_TRUSTED_PROXY_CONFIG` to that absolute file path in the Compose environment and recreate the frontend. The file is mounted read-only; it is not baked into the image. Configure the TLS edge to replace incoming client forwarding headers with the real peer address, or use a correctly maintained chain with only explicitly trusted hops.
4. On private HTTPS staging, prove that separate real clients receive independent budgets and that varying forged forwarding headers cannot bypass one client's budget. Record the chosen topology and acceptance result before launch.

Until step 2 is complete, users behind the same TLS proxy share its IP budget. That conservative default prevents spoofing but is not production acceptance of your future proxy configuration. Do not disable the limiter to work around it.

## Storage, failure handling and validation

The limiter uses the configured Redis host/port/database, with one-second connection and command socket timeouts and its own key prefix. The production Redis profile uses AOF persistence and `noeviction`. API restarts preserve counters; Redis loss/restore or JWT-secret rotation can reset budgets. Never clear all Redis data to unblock one login, because the same service also supports other application features. No per-account administrative unlock endpoint is added; wait for expiry.

Tests cover endpoint/path normalization, mandatory production enforcement, IP normalization and header spoofing, 429/CORS/request IDs, redacted failure behavior, and real Redis concurrent callers, expiry and bounded counters. The production smoke workflow exercises actual Nginx/API/Redis limits with forged headers, checks budgets survive API and Redis recreation, then stops Redis to verify 503 without bypass. Desktop/mobile browser tests cover the wait message and explicit retry.

This completes the auth-IP-budget portion of the P1 abuse item. [Property action budgets](property-action-limits.md) additionally protect inquiries, messages, reports and property-photo uploads by IP and account. Account-targeted/distributed auth defenses, Google OAuth and legacy endpoint budgets, session/token storage review, broader ownership/security-header checks, monitoring and actual hosted proxy acceptance remain open. These limits do not justify public launch before the remaining P0/P1/P2 requirements.

References: [Redis counter/rate-limit patterns](https://redis.io/docs/latest/commands/incr/), [Nginx trusted real-IP configuration](https://nginx.org/en/docs/http/ngx_http_realip_module.html).
