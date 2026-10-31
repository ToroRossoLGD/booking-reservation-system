# Personal reminder delivery history

Open reminder settings on the stay or rental/sale inquiry pages, then **Istorija isporuke podsetnika**. History loads only when requested and shows 20 records per page, newest first. Use refresh to return to the newest page or retry a failed request.

Each entry shows the reminder category, reservation/inquiry ID, scheduled date/time and the time it was created in the application. Stay dates remain date-only; viewing and creation timestamps are explicitly UTC. These are historical snapshots: a later date change, cancellation or withdrawn inquiry does not rewrite an earlier reminder. Check the actual reservation or conversation for the current arrangement.

Records confirm that the inbox notification was created atomically with its delivery record. They do **not** confirm that the user read it, that an email or push was delivered, or that a scheduled reminder failed. Skipped, pending and failed attempts do not appear. Dismissing inbox notifications retains delivery history and duplicate protection. No new sending or retry action is introduced by opening history.

## API and deployment

- `GET /notifications/stay-reminders/history?offset=0`
- `GET /notifications/viewing-reminders/history?offset=0`

Both require authentication, derive the recipient from the current account, and return private/no-store responses. Owners and administrators also see only their own recipient records. Responses contain `items`, `offset` and `has_next`. Items contain only `id`, `kind`, `reference_id`, `scheduled_for` and `created_at`; no other participant IDs, messages or contact data are exposed.

Ordering uses creation time and ID to resolve ties. Offset pagination can shift as new reminders arrive; refresh to restart at the newest page. Existing delivery records are included without backfill. Apply migration `b49d60ef5378` to add the two recipient/time/ID indexes; no notification or delivery data is rewritten.

This completes personal in-app reminder visibility only. Email/push transport, external delivery receipts and failure tracking remain open P2 work.
