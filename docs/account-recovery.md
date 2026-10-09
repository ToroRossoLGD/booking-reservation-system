# Password recovery

The login dialog links to `/forgot-password`. A valid email submission returns the same public confirmation whether the account exists or not. Known accounts receive a one-use link to `/reset-password#token=...` on the configured `FRONTEND_URL`; the request Host header never controls this link. The token is random, stored only as a SHA-256 hash and expires after `PASSWORD_RESET_EXPIRE_MINUTES` (30 by default, permitted range 1-1440).

The browser reads the fragment before React mounts and removes it with `replaceState`. It keeps the token in page memory, not local/session storage. Fragments do not travel in HTTP requests or Referer headers. Reloading the cleaned page loses the token; reopen the email link or request a new one. Avoid third-party scripts on recovery pages and redact request bodies in any proxy/APM logging; the confirmation POST necessarily contains the token and new password.

Confirmation checks matching passwords in the UI and bcrypt's 72-byte UTF-8 limit at the API. Success consumes the token, invalidates remaining reset tokens, increments the account token version and revokes its API keys in one database transaction. The browser clears its previous bearer token and offers normal login; there is no automatic login. Expired, reused and invalid links offer a new request. PostgreSQL locks serialize issuance/consumption for the same account, so concurrent requests leave one active link and concurrent confirmation has one winner. No migration is required.

## SMTP configuration

- `SMTP_MODE=disabled`: no email is sent. Reset requests return 503 before looking up the email address. Production templates intentionally start in this state until a provider is configured.
- `SMTP_MODE=plain`: unauthenticated local development, for example MailHog on port 1025. Production rejects this mode unless the demo blocks all mail anyway. Credentials are never accepted with plaintext mode.
- `SMTP_MODE=starttls`: explicit TLS upgrade (typically port 587), certificate/hostname verification, then optional username/password authentication. Upgrade failure stops delivery; there is no plaintext fallback.
- `SMTP_MODE=tls`: implicit TLS (typically port 465), verified certificates and optional authentication.

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` and `SMTP_FROM_NAME` for the chosen provider. Both credentials must be set or both omitted for an authenticated-by-network TLS relay. `SMTP_TIMEOUT_SECONDS` defaults to 10 (range 1-60). Passwords are runtime secrets and must never enter frontend build variables. Existing production installations must explicitly select `disabled`, `starttls` or `tls` before upgrading; the old default plaintext configuration now fails startup.

Before inviting users, verify the sender/domain with the provider and complete a real delivery/recovery round trip on private HTTPS staging, including spam-folder behavior. CI checks TLS configuration and failure paths with mocked SMTP, real PostgreSQL concurrency/session revocation and desktop/mobile browser flows. It does not prove external inbox delivery or provider credentials.

## Failure and deployment boundaries

Reset email is attempted as an in-process background task after the generic response. Failure logs only `Password reset email delivery failed`, never recipient, token, body or raw provider exceptions. The user can request a new link, which invalidates the previous one. There is no durable mail outbox or automatic retry yet: a process interruption can lose a pending email, and a successful SMTP handoff does not guarantee inbox delivery. Alert on delivery failures in the P1 monitoring work.

Demo mode rejects both reset endpoints and sends no email. Public response text does not reveal account existence; this is not a claim of constant-time behavior. [Email ownership verification](email-verification.md) now protects new property bookings and inquiries. Rate limiting, real provider acceptance and stronger abuse/session hardening remain open P1 gates. Keep access controlled until those gates and the project's P0/P1/P2 launch requirements are complete.

References: [Python SMTP/TLS API](https://docs.python.org/3/library/smtplib.html), [OWASP password recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).
