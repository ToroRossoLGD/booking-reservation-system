# P2: owner occupancy calendar snapshot

Open **Owner panel → Blokade** for a short-stay property and choose **Preuzmi
zauzetost (.ics)**. The file is generated on each explicit click. Errors retain a
retry action. It represents occupancy, not the full set of booking rules.

`GET /owner/properties/{property_id}/occupancy.ics` requires the signed-in venue
owner or an administrator. Other accounts cannot export it. The response uses
`text/calendar`, an attachment filename and `Cache-Control: private, no-store`.
No bearer token appears in a downloadable URL and no public feed is created.

## Export semantics

- Window: today in the property's timezone through today + 365 days, end exclusive.
- Includes confirmed stays for the whole venue, even those booked through another
  listing, active owner blocks and the shared inventory's preparation gap.
- Intervals are clipped to the window and overlapping/adjacent dates are merged.
- Cancelled stays and removed blocks are excluded. Empty occupancy yields a valid
  calendar with no events. A withdrawn short-stay listing can still export its
  existing occupancy; non-short-stay listings are rejected.
- Events are all-day, with generic `Unavailable` summaries. The file contains no
  guest/contact information, listing titles, addresses, prices or block reasons.
- Date-only start/end follow [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html),
  with an inclusive start and exclusive end, avoiding UTC/DST date shifts.
- UIDs are deterministic for the deployment, venue and merged date interval, so
  aliases export the same identity. They can change when intervals/window change.

## Limits and next steps

This is a manual snapshot, not a subscription URL or two-way synchronization.
Import into a separate external calendar that can be replaced on later exports.
Repeated imports may duplicate events; cancellations and date changes do not
remove previously imported events automatically. Refresh the snapshot and replace
the previous imported calendar rather than treating it as live availability.

Unoccupied dates are not a promise of bookability: minimum stay, notice, booking
horizon, guest limits, publication and other rules still apply in Bookica. External
platform acceptance has not yet been demonstrated. Do not rely on this snapshot
alone to prevent competing bookings on multiple channels.

Next P2 slices are hashed/revocable feed credentials, subscription export, safe
external ICS import, refresh jobs and conflict/last-sync UI. Legacy hourly calendar
feeds remain separate. P1 and the parent P2 synchronization item remain open.

## Validation

Backend tests exercise shared inventory, privacy, cancellation/removal, merged
preparation gaps, window clipping, owner/admin authorization, missing/wrong-type
listings and HTTP authentication/headers. Browser coverage exercises export failure,
retry, authenticated download and the existing block-management flow. No schema
change or Alembic migration is needed.
