# Nightly stay notifications

When a guest confirms a nightly stay, both the guest and the current venue owner
receive a private in-app notification. Cancelling before arrival creates a second
notification for each participant. Messages include the reservation number,
listing title and stay dates in the reservation's timezone; confirmations also
show the saved amount and pay-at-host terms.

Open **Obaveštenja** from `/stays` or `/owner/stays`, or use the notification link
in the owner property manager. `/account/notifications` opens the inbox directly
after authentication. Each stay notification links to the recipient's guest or
owner reservation list. Lists remain permission-scoped by the existing APIs.

The inbox supports marking messages read, dismissing messages, clearing read
messages, refreshing and paging through older notifications. The displayed unread
count applies to the current page. Updates appear on refresh; there is no polling.

Notifications commit in the same transaction as the reservation/status change.
Existing account/stay row locks serialize repeated requests, and each event has a
unique recipient-specific deduplication key. Retrying a booking or cancellation
does not recreate notifications, even if the recipient has dismissed one. A
failed notification write rolls back the reservation change too.

Run `alembic upgrade head` before deployment. Migration `eb613f768029` adds a
nullable action path to notifications; existing messages keep their content and
have no navigation action. Old reservations are not backfilled with notifications.

This release covers in-app confirmation/cancellation events for nightly stays.
It does not send email, browser push notifications or scheduled reminders. Rental
inquiries and sales do not generate these stay notifications.
