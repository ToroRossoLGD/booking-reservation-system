# Owner property analytics

Open `/owner/analytics` from the listing manager or owner reservation page. Select a year (2000–2100) and optionally a listing. The panel shows totals, a switchable monthly chart, and a horizontally scrollable monthly table on small screens.

## Metric definitions

- **Views:** recorded openings of a listing's detail page or expanded card, across every offer type. Merely showing a search result does not count. One listing/session/day counts once (UTC), including repeated requests or React remounts. Authenticated owners' views of their own listings are excluded.
- **Confirmed reservations:** currently confirmed nightly reservations grouped by arrival month, including future bookings. This is not the number of bookings created that month or proof of physical attendance.
- **Cancelled reservations:** currently cancelled nightly reservations grouped by their original arrival month; cancellation does not contribute nights or value.
- **Nights:** confirmed nights allocated to the months in which they occur; checkout is exclusive. A stay crossing a month/year boundary contributes nights to each corresponding period, but its reservation count belongs only to its arrival month.
- **Booked value:** the saved agreed total distributed proportionally over nights, with cumulative integer rounding preserving the full total. Each currency is separate. This is not cash received, profit, or payment reporting; nightly payments currently occur at the property.

Existing reservation history can be analyzed immediately. Views start only after this feature is deployed and cannot be reconstructed for earlier periods. Zero views means no recorded views, not necessarily zero actual visits. Empty months remain visible. Unpublished listings retain their analytics; access follows current venue ownership. Admin analytics uses the same own-venue scope.

## Collection and privacy

The frontend stores a random UUID in sessionStorage, rotating it daily. The backend stores only a keyed hash scoped to listing and UTC date, plus listing ID and date; it does not persist the UUID, IP, account ID, email or user agent in the view table. Raw hashes are not returned to owners. The database uniqueness constraint and conflict-safe insert prevent concurrent duplicate counts.

Tracking failures do not block reading or booking. Do Not Track and unavailable sessionStorage disable collection. Counts are approximate session-based interest, not unique people or audited traffic: new sessions, automated requests and client manipulation can affect them. This version has no bot detection or automatic retention job.

## API and deployment

- `POST /properties/{id}/views` accepts `{visitor_id: UUID}` for published listings and returns 204. Authentication is optional; supplied credentials must be valid. Authenticated owner views return 204 without recording.
- `GET /owner/property-analytics?year=2026&property_id=7` requires owner/admin. The listing filter is optional. Responses contain the owner's listing choices and all twelve monthly aggregates. Selecting another owner's listing returns 404.

Run `alembic upgrade head` before deploying the API/frontend. Migration `c94f1d546807` creates `property_views`; downgrade removes collected view data without changing reservations or listings.

Tests cover day deduplication, owner exclusion, private ownership scope, month/year boundaries, leap years, currency separation, rounding, cancellation, empty periods, migration round-trip and concurrent inserts on PostgreSQL. Frontend/browser checks cover filters, charts, tracking retries and mobile layout.
