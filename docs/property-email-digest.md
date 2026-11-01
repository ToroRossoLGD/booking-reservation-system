# Opt-in property notification email digest

Open **Email sažetak obaveštenja** in `/account/notifications`. A verified account can explicitly enable an hourly or daily email summary of newly created property notifications. The feature starts disabled both per account and server-wide. Disabling it leaves the in-app inbox and reminder preferences unchanged. A message already being sent may still arrive after disabling.

Eligible notifications are those linking to `/stays`, `/owner/stays`, `/rentals`, `/owner/rentals`, `/sales` or `/owner/sales`. This includes booking/inquiry lifecycle notifications and enabled reminders. Legacy hourly reservations, calendar health notices and other categories are excluded. Read notifications are still eligible; notifications dismissed before collection are not. Each summary contains only the count (up to 20) and a link to the authenticated inbox, never titles, conversation messages, guest details or contact information.

Enabling or re-enabling sets an ID baseline at the account's latest existing notification, so old inbox items are not emailed. Accepted items are individually recorded instead of advancing a delivery cursor, ensuring notifications committed out of ID order after opt-in are not lost. Larger backlogs drain in batches of 20 per scheduled attempt. The summary is not a real-time reminder or a guarantee of timely viewing/arrival alerts.

## Frequency

Choose **Jednom na sat** (1 hour, default) or **Jednom dnevno** (24 hours). Selection saves immediately without changing whether email is enabled. A changed interval schedules the next check one selected interval from saving; it preserves the opt-in baseline and all pending notifications. An unchanged interval leaves the schedule untouched. Already-claimed SMTP work is allowed to finish; changing frequency is not an immediate stop operation.

Daily means a rolling 24-hour interval, not delivery at a fixed local wall-clock time. The panel shows the next planned check in UTC while enabled. No email is sent without eligible new notifications; scheduler delays can postpone execution. Idle accounts are checked at the chosen interval, too. Failure retries remain 15 minutes apart and still disable after three failures, regardless of normal frequency.

Migration `d61f82ab7590` preserves existing accounts at one hour and adds a database constraint allowing only 1 or 24. Deploy the migration before API/worker code and restart both. Old API clients omitting `interval_hours` retain the saved choice; selecting a daily interval while disabled does not opt the user into email.

## Operator setup

1. Apply `alembic upgrade head`, including `c50e71fa6489` and `d61f82ab7590`.
2. Configure the existing SMTP service and a trusted `FRONTEND_URL`. Production requires the existing secure SMTP configuration.
3. Set `PROPERTY_EMAIL_DIGEST_ENABLED=true` on API and worker; `SMTP_MODE=disabled` and demo mode always suppress execution. No account is automatically enrolled.
4. Run Redis, Celery worker and beat. `send_property_email_digests` runs every five minutes, processing at most ten due accounts per invocation. Accounts are checked at their chosen interval. Monitor queue/task duration and provision capacity for account volume.
5. Verify opt-in, real provider acceptance, inbox/spam receipt, disable and failure recovery on private staging before enabling for public users. Automated tests mock the mail sender; real external delivery has not been verified by this change.

## Reliability and status

Claims use PostgreSQL `FOR UPDATE SKIP LOCKED`, a random lease token and a ten-minute lease. SMTP executes outside a database transaction after rechecking consent, verified email and the current account address. The claim advances its next check by the selected interval; abandoned work becomes eligible once both its lease and next-run time permit it. Task limits are 240 seconds soft and 270 seconds hard.

Successful SMTP submission records the included notification IDs and `accepted` status atomically. This means **accepted by SMTP**, not delivered, read or guaranteed to avoid spam. Failures use sanitized status, retry after 15 minutes, and disable the preference after three consecutive failures. Re-enable after correcting the cause; the new baseline intentionally skips previous pending items, which remain accessible in the inbox. Losing email verification disables the preference until the account verifies and opts in again.

SMTP and database commits cannot form one transaction. A provider may accept a message just before an error, worker crash or database failure; retry can send a duplicate count summary. This is explicitly not exactly-once email delivery. Delivery-marker records survive inbox dismissal and contain only user/notification IDs. Providers' delivery receipts, bounces, complaints, push transport and per-event/channel preferences remain future work. Do not log SMTP credentials, recipient addresses or message bodies in worker tracing.

## API

Authenticated `GET /notifications/email-digest` returns `enabled`, server `available`, account `verified`, `interval_hours`, `next_run_at`, `last_status`, `last_attempt_at` and `last_accepted_at`. `PUT` requires a strict `enabled` boolean and optionally a strict integer `interval_hours` of 1 or 24. Omission or null preserves the saved interval. The account/address comes from authentication, not the request body. Responses are private/no-store and never expose email addresses or delivery identifiers. Disabling remains available when server delivery is off; demo mode rejects mutations.

Status reflects the last completed attempt and may remain pending without new eligible notifications. Opening the panel or explicitly refreshing reloads status; it does not send email. Operational monitoring is still necessary for stopped workers or scheduling delays.
