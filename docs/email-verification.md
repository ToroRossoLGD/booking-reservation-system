# Email ownership verification

Password signup creates an **unverified** account and queues an email when SMTP is enabled. Login and browsing remain available. A signed-in user can request another link at `/verify-email`; the request endpoint only uses the authenticated account's stored email, never an arbitrary recipient supplied in the body.

`POST /auth/email-verification/request` returns a generic message. A per-account 60-second cooldown serializes concurrent resends; a newly issued link invalidates previous links. This cooldown is not a substitute for the broader P1 IP/account rate limits.

The random link points to the configured `FRONTEND_URL/verify-email#token=...`. Only a SHA-256 hash is stored, along with the user ID, email snapshot and expiry. `EMAIL_VERIFICATION_EXPIRE_MINUTES` defaults to 60 (range 1-1440). The browser removes the fragment before React mounts, retains it only in memory and requires an explicit button click before sending `POST /auth/email-verification/confirm`. Opening a link or an email scanner's GET does not consume it. Reloading the cleaned page requires reopening the email link. Redact confirmation bodies in proxy/APM logging and avoid third-party scripts on this page.

Confirmation locks the account, checks expiry and the stored email, records `email_verified_at` and consumes all active verification links in one transaction. Replayed links fail; concurrent confirmations have one winner. It does not log the user in, change their password or invalidate their sessions. Google login marks the address verified only after validating the provider's signed, verified email; an existing Google subject whose email differs from the local stored address does not verify that old address.

## Protected actions and migration

Run `alembic upgrade head` before starting the updated API. The additive migration adds a nullable timestamp and a separate verification-token table. **Existing accounts remain unverified**, including owners and admins. There is no automatic backfill or public override.

Outside isolated demo mode, the API requires a verified account for:

- `POST /properties/{id}/stays`: a new nightly reservation.
- `POST /properties/{id}/rental-inquiries`: a new rental inquiry.
- `POST /properties/{id}/sale-inquiries`: a new purchase inquiry.

The guard applies to both bearer and API-key authentication and all roles. Public browsing/quotes, existing reservation access/cancellation and ongoing inquiry conversations remain available. Owner publication and the legacy hourly booking API are outside this initial contact-verification gate and still require the P1 authorization/abuse review. This verifies account email ownership, not a listing's separately entered contact details, identity, phone number or property ownership.

Existing users can sign in, follow the account notice and resend a link. If an email-change flow is added later, it must clear verification, invalidate outstanding links and use the same account lock. No email-change flow is introduced here. Downgrading the migration deletes verification history and should only accompany rollback to the previous API.

## Delivery and acceptance

Use the [SMTP configuration](account-recovery.md#smtp-configuration), a verified sender/domain and a correct HTTPS frontend origin. With `SMTP_MODE=disabled`, registration still succeeds but no verification mail is queued; manual requests return 503 and protected actions remain blocked. Configure delivery before inviting real users. `DEMO_MODE=true` disables verification mail and confirmation, and exempts fictional demo accounts from the gate.

Mail delivery runs as an in-process background task. Errors log only `Email verification delivery failed`; responses never contain the raw token. There is no durable outbox or automatic retry. A crash or delivery failure can lose a message; wait at least one minute and resend, which invalidates the old link. Provider handoff does not prove inbox delivery.

Automated checks cover migration preservation/rollback, token validation, server-side gates, SMTP-disabled behavior, redacted failures, PostgreSQL resend/confirmation races, and mocked browser flows on desktop/mobile. Before checking off the P1 parent milestone, use private HTTPS staging to verify real signup delivery, confirmation, resend/old-link rejection, existing-user verification and password recovery with the configured provider. Record the commit and results without storing raw tokens or recipient data in public logs.
