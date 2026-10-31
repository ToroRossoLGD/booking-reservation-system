# Nightly stay reminders

Guests and current apartment owners receive an in-app reminder the day before check-in and check-out, starting at 09:00 in the timezone saved on the reservation. The message includes the saved check-in/out time when available, otherwise asks the user to confirm it. It links to the guest or owner reservation list. This does not send email or push notifications and does not cover rental/sales viewings.

## Preferences

Open **Podsetnici za dolazak i odlazak** on `/stays` or `/owner/stays`. The setting applies to the signed-in account, across both guest and owner reservations. Preferences default to enabled; the worker feature is disabled globally until an operator enables it. Turning reminders off does not disable booking confirmations/cancellations or remove existing notifications. A reminder already in progress may still arrive.

Authenticated `GET` and `PUT /notifications/stay-reminders` read/update `{ "enabled": true }`. Writes require a strict boolean and reject extra fields. The recipient always comes from authentication, never the request body. Responses are private/no-store; demo mode rejects changes and suppresses worker execution.

## Scheduling and delivery

Apply migration `f27b48cd3156`, set `STAY_REMINDERS_ENABLED=true` on the worker and run Redis, Celery worker and beat. Beat invokes `send_stay_reminders` every five minutes. Restart the worker after configuration changes. Existing scheduler/worker health monitoring remains required.

Workers process candidate reservations in batches of 100, locking listing, venue and stay in the same order used by date changes. Each reservation is rechecked for cancellation, current dates and owner before notification creation. Delivery records and inbox messages commit together. Concurrent workers cannot duplicate a reminder; dismissing a notification does not remove its durable delivery record. A changed event date can receive a new reminder. Changing it back to an already reminded date does not resend that reminder. Previously sent messages remain historical; open the reservation for current details.

Only the local day before the event is eligible, from 09:00 until midnight. A worker recovering later that day catches up; missed reminders are not sent on arrival/departure day. Both UTC date boundaries and daylight-saving changes use the reservation's IANA timezone. Invalid timezone rows are skipped. Paused/offline workers cannot guarantee timely delivery.

Task limits are 240 seconds soft / 270 seconds hard. Large candidate volumes require monitoring task duration and scaling or further queue partitioning before relying on timely completion. Durable records contain recipient, reservation, event type/date and creation timestamp; they contain no email address or provider URL. No SMTP delivery status is implied by these records.

Before public use, verify scheduling, restart recovery, opt-out and inbox visibility with real reservations in private staging. Email/push transport, per-channel preferences and viewing reminders remain open P2 work.
