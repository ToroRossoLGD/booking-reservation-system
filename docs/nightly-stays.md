# Nightly apartment reservations

## Rollout

Run `alembic upgrade head` before restarting the API and serving the updated
frontend. Revision `d5f0b3c8e721` adds the `stays` table and property booking
settings. Existing listings remain contact-only (`booking_enabled=false`).
Existing hourly reservations and their payment flow are not converted.

As an owner, open `/owner`, edit a short-stay listing, set maximum guests,
minimum nights and the apartment's IANA timezone, then enable whole-apartment
reservations. The asking price becomes the fixed nightly rate. Booking is
available only while the listing is published and enabled.

Each venue represents **one whole apartment** for nightly inventory. Multiple
listings referring to that venue share occupancy. Create a separate venue for
each independently rentable apartment. Venues with hourly resources cannot
enable nightly booking; a venue with nightly booking enabled or stay history
cannot add hourly resources. This prevents two independent reservation systems
from selling the same apartment's availability. Existing hourly venues keep
working as before.

## Guest flow

1. Expand a short-stay listing and review its monthly occupancy calendar.
2. Select arrival, departure and guest count, then request a server quote.
3. Confirm while signed in. The server rechecks current pricing and occupancy.
4. View the confirmed stay at `/stays` (also linked from the account dashboard).
5. Cancel without a fee before the arrival date, in the apartment's timezone.

Reservations are confirmed immediately with **payment at the property**. There
is no online charge, deposit, refund transaction or pending-payment hold in this
release. The UI explicitly displays these terms before confirmation. Owners can
set local arrival/departure times for nightly listings. See [stay times](stay-times.md)
for validation, quote checks, reservation snapshots and migration instructions.

Owners view reservations and guest contact emails at `/owner/stays`. Guests can
only list/cancel their own stays. Public calendars expose occupied dates only,
never guest identities or reservation IDs. Host contact and property title,
city, timezone, arrival/departure times, nightly price and total are snapshotted at booking.

## Dates, price and concurrency

- Arrival is tomorrow or later in the property's timezone; departure must be
  within 365 days. Stays last 1–90 nights and respect the owner's minimum (1–30).
- Guests must fit the owner's maximum (1–100), but booking always occupies the
  whole apartment. Price is per apartment/night, not per guest.
- Calendar dates are stored as `DATE`. Nights are the difference between dates,
  including across daylight-saving transitions; no division of elapsed hours.
- Occupancy is half-open: `[arrival, departure)`. Another guest may arrive on
  the previous guest's departure date. Cancelled stays do not block occupancy.
- Quote requests are advisory. Creation locks the account, listing and venue,
  then rechecks occupancy under the venue lock before committing. Listing
  updates use compatible locks. This assumes PostgreSQL's default READ COMMITTED
  isolation, as used by the application.
- The client submits a UUID request ID and the quoted total/currency. A changed
  price yields 409 and requires another quote. Retrying the same request returns
  the existing stay, including a cancelled stay; it never reactivates it.
- A listing with stay history cannot be moved to a different venue. Database
  foreign keys preserve booking history instead of cascading it away.

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /properties/{id}/stay-quote` | Quote dates and guest count |
| `GET /properties/{id}/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD` | Occupied intervals, maximum 93-day range |
| `POST /properties/{id}/stays` | Authenticated, idempotent confirmation |
| `GET /stays/mine?offset=0&limit=20` | Guest reservations |
| `GET /owner/stays?offset=0&limit=20` | Owner reservations and guest email |
| `POST /stays/{id}/cancel` | Guest cancellation before arrival day |

The quote body is `{check_in, check_out, guests}`. Creation adds `request_id`,
`expected_total_cents` and `expected_currency`. Amounts use integer minor units.
Lists are paginated; administrators' owner lists cover their own venues, not
every owner's reservations.

## Validation and remaining work

`STAY_TEST_POSTGRES=1 pytest tests/test_stays.py` exercises simultaneous booking
and retry requests against a unique temporary PostgreSQL schema. CI enables
this test. Migration tests check old listing preservation and disabled defaults.
Browser tests cover quote → confirmation → account view → cancellation, with
deterministic API fixtures; component tests cover stale quotes and safe retries.

Seasonal prices, external calendar imports, online payments, automated guest
emails, owner cancellation, rescheduling and
long-term lease workflows remain separate work. Do not enable booking for a
property also advertised elsewhere until its external reservations can be
accounted for operationally; external calendar sync is not implemented.
