# Confirmed viewing reminders

The renter/buyer and owner recorded on a rental or sale inquiry receive one in-app reminder during the final 24 hours before a confirmed viewing. Proposed, declined, closed, withdrawn, missing-time and already-started viewings are excluded. Participants follow the existing inquiry conversation, even if the listing changes ownership afterward; the new owner does not gain access to an earlier conversation through reminders.

The message contains the listing title and explicit UTC appointment time, with a link to the relevant rental/sales inbox where the existing interface displays local time. It contains no inquiry message, contact address or private reply. Reminders use a rolling 24-hour window rather than a calendar-day rule, so a viewing confirmed shortly before its start is still eligible while it remains in the future.

## Preferences and activation

Open **Podsetnici za razgledanja** on `/rentals`, `/sales`, `/owner/rentals` or `/owner/sales`. This account-level setting controls both rental and sale viewing reminders, independently of nightly stay reminders. Preferences default to enabled; the worker feature defaults to disabled. Existing confirmations and conversation notifications are unaffected. Previously sent notifications remain; an already-running reminder may finish after opt-out.

Authenticated `GET` and `PUT /notifications/viewing-reminders` read/update `{ "enabled": true }`. Writes reject non-boolean and extra fields, derive the account from authentication, and are unavailable in demo mode. Responses are private/no-store.

Apply migration `a38c59de4267`, set `VIEWING_REMINDERS_ENABLED=true` in the worker environment, and run Redis, Celery worker and beat. The `send_viewing_reminders` task runs every five minutes. Demo mode suppresses execution. No email/push messages are sent.

## Reliability and limits

Each inquiry is locked and rechecked before processing. Durable delivery records and inbox messages commit atomically; concurrent workers and retries cannot duplicate the same inquiry, recipient and viewing time. Dismissing an inbox message retains the delivery record. A changed and reconfirmed time can receive another reminder. Returning to a previously reminded time does not resend it. Existing messages remain historical; check the inquiry for current details.

After an outage the worker catches up only while the viewing is still in the future and within 24 hours. It does not send late reminders after the appointment. Both inquiry types use ID pagination in batches of 100. Monitor processing time, failures and scheduler health; the task has a 240-second soft and 270-second hard limit, and large volumes may need queue partitioning. A delivery record confirms inbox creation, not email receipt or that the user read it.

Private staging acceptance of scheduling, recovery, preferences and real-user inbox visibility remains required. Email/push transport and channel-specific delivery tracking remain open P2 work.
