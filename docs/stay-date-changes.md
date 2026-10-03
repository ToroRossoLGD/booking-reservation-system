# Guest-requested stay date changes

Guests can open **Promene termina** on a reservation at `/stays`, choose new
dates, inspect a current nightly quote and explicitly agree to its price and
terms before submitting. Owners open the same section at `/owner/stays` to
approve or decline. The guest can withdraw a pending request. Both participants
receive in-app notifications for submission and each decision.

This applies only to confirmed nightly stays before arrival. The guest count
stays unchanged. Rental and sales listings are not part of this flow. Payment
remains with the host; no online payment, refund or deposit is created.

## Availability and price

A pending request **does not reserve the proposed dates**. The original dates
and booked price remain active until approval. On approval, Bookica rechecks
publication/booking status, guest capacity, minimum/maximum nights, advance
notice, booking window, seasonal prices, local arrival/departure times, shared
venue occupancy, preparation gaps and owner blocks. The reservation being
changed is excluded from conflicts, allowing partially overlapping date moves.

Any changed quoted terms require the guest to withdraw and request a fresh
quote; the owner cannot silently change the accepted price. An unavailable
proposal leaves the original reservation unchanged. Approving updates the
dates and price/time snapshot atomically with request history and notifications.
The current calendar, search availability, stay lists, exports and analytics
then use the new reservation dates. Previously downloaded calendar files are
static copies and should be replaced by a new download.

## State, retries and access

- At most one pending request exists per reservation. Each request retains the
  original reservation snapshot, proposed dates, quoted terms and timestamps.
- Only the booking guest can quote, submit or withdraw. Only the apartment's
  actual owner can accept or decline. Unrelated users receive 404, including
  for history and individual decisions.
- Request UUIDs are bound to their submitted payload. Identical retries return
  the existing request, including after a decision; conflicting reuse returns
  409. Repeating a completed decision is idempotent and emits no new notification.
- Cancellation or reaching either the original or proposed arrival day makes
  an unresolved request inactive. History reports it as `expired` immediately,
  computed at read time; `resolved_at` can remain null. A new submission closes
  an expired pending record before creating another one, if the stay is still
  eligible. Expiry itself does not send a notification.
- Approvals and submissions acquire recipient user key locks before locking
  listing, venue, then stay, using the same
  inventory lock as new bookings and blocks. A conflicting reservation cannot
  be confirmed concurrently on another listing for the same apartment.
- Original booking retries after rescheduling can return a stale-payload 409;
  they never create a second stay. Refresh the stay list for its current terms.

## API and deployment

All endpoints require login:

| Endpoint | Purpose |
| --- | --- |
| `POST /stays/{id}/date-change-quote` | Quote new `check_in`, `check_out`, unchanged `guests` |
| `GET /stays/{id}/date-changes?offset=0&limit=20` | Participant-only paginated history, newest first |
| `POST /stays/{id}/date-changes` | Submit dates, guests, `request_id` and the complete returned `quote` |
| `POST /stays/{id}/date-changes/{change_id}/decision` | `action`: `accept`, `decline` or `withdraw` |

Run `alembic upgrade head` (revision `fcd806435790`) before deploying the updated
API and frontend. Existing reservations remain unchanged and start without
change requests. This flow does not require a new worker or external provider.
