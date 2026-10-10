# Account-wide logout

Open **Bezbednost naloga** from the account dashboard (`/account/security`), then
confirm **Odjavi sve uređaje**. This is available to every authenticated role,
including accounts that have not yet verified their email.

`POST /auth/logout-all` authenticates the caller using the existing bearer/API-key
dependency. It accepts no target account identifier. A successful response is
`204` with `Cache-Control: no-store`. In one database transaction it locks the
user, increments `users.token_version`, and revokes their remaining API keys.
Previously revoked keys retain their timestamps. No migration is necessary.

Old bearer tokens and revoked keys fail subsequent authentication. A new login
works with the unchanged password; integrations need newly generated API keys.
Other accounts, reservations and recovery links are unchanged. Ordinary **Log
out** remains a local browser logout. The security page removes its local token
only after success or an explicit 401; a network/server error permits retry and
does not claim success. A lost success response can therefore require signing
in again before confirming account-wide revocation.

Concurrent requests authenticated before revocation may finish. This is not a
live device registry, a cancellation mechanism for in-flight requests, or
per-device revocation. Keys created after the revocation transaction (including
an already authenticated in-flight creation) are outside its snapshot. A stale
concurrent logout cannot invalidate sessions issued after an earlier revocation.
Someone who knows the password can sign in again: use password recovery if the
password is compromised. No new Redis budget is imposed on this endpoint, so
an unavailable limiter does not prevent credential revocation.

Tests cover atomic rollback, account isolation, stale credentials, fresh tokens,
concurrent PostgreSQL revocations, authenticated routing, confirmation/cancel,
retry and desktop/mobile browser flows. PostgreSQL and browser coverage run in
CI. Private staging acceptance remains open. Tokens still use the existing
localStorage approach; XSS/token-storage review, wider authorization review and
the remaining abuse controls are separate P1 work.
