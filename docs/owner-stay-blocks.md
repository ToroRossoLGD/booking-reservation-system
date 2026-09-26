# Owner calendar blocks

In `/owner`, choose **Zauzetost** next to a property. For a short-stay listing,
enter the first unavailable date, the first available date afterwards, and an
optional private reason. Choose **Blokiraj termin**. Remove a block with
**Ukloni blokadu** and confirm the removal.

Blocks belong to the whole venue, so every listing for that venue shares them.
They work for drafts and listings where online reservations are not yet enabled.
Only short-stay listings can create new blocks. Existing blocks remain manageable
after withdrawal or an offer-type change. A listing cannot change venue while
its current venue has active blocks; remove them first.

## Availability rules

- Dates are half-open: the final date is available for a new arrival.
- A block covers 1–365 nights, starts today or later in the selected property's
  timezone and ends within the next 365 days.
- Confirmed reservations and existing active blocks reject overlapping blocks
  with HTTP 409. Blocking never cancels or changes an existing reservation.
- Quote, booking confirmation, public calendar and date-filtered search all
  respect blocks. Public calendars expose only unavailable date ranges, never
  the private reason, creator or block identifier.
- Removing a block reopens its dates unless another reservation occupies them.
  Other booking rules (capacity, minimum nights and booking window) still apply.

Creation and removal lock the listing then the venue, matching the reservation
flow's lock order. The shared venue lock serializes block creation against
bookings through any listing alias. PostgreSQL concurrency coverage runs in CI.

Each creation request has a UUID `request_id`, unique per venue. Repeating the
same payload returns the existing active block. Reusing the ID for different
data, or retrying a removed block, returns 409. Removal is idempotent and retains
an inactive record so delayed retries cannot silently recreate a removed block.

## API and access

All endpoints require an owner of the venue or an administrator:

- `GET /owner/properties/{id}/stay-blocks?offset=0&limit=20`: active blocks,
  ordered by start date and ID, with total and pagination metadata.
- `POST /owner/properties/{id}/stay-blocks`: `check_in`, `check_out`, optional
  `reason` (up to 300 characters), and `request_id`.
- `DELETE /owner/properties/{id}/stay-blocks/{block_id}`: deactivate a block
  belonging to that property's venue; returns 204, including repeated removal.

No external calendar imports, subscriptions or synchronization are included.
Use a private reason to identify an off-platform booking if entering it manually.
Past active blocks remain in the owner's list until removed.

## Deployment

Run `alembic upgrade head` before serving the updated API. Migration
`e50b7f102463`, after `d49a6e0f1352`, creates `stay_blocks` and its constraints.
Existing reservations and listings are unchanged. Downgrading deletes all block
records and removes their availability protection; use the corresponding older
application version only after accounting for those dates.

Checks include schema validation, ownership, aliases, boundary dates, retries,
removal, privacy, search/quote/booking integration, migration round trip, UI
conflicts and desktop/mobile management. The PostgreSQL race test additionally
checks that an overlapping booking and block cannot both succeed.
