# Import an occupancy snapshot

Owners and administrators can select an `.ics` file in a short-stay listing's availability panel, choose **Pregledaj uvoz**, review the dates and choose **Potvrdi uvoz blokada**. Preview never writes data. Confirmation checks current availability again while holding the apartment lock shared by booking creation. If any range conflicts, no ranges are written and the response identifies the conflicting dates.

Imported dates become ordinary private blocks shared across all listings of the apartment, and immediately affect availability, search and new bookings. Remove them individually in the existing block list. Existing reservations and blocks are never overwritten or cancelled. An exact active block is reported as already present, making an immediate retry safe from duplicate blocks. An overlapping block with different boundaries is a conflict. Reservation preparation gaps also count as occupied.

## Supported files

- UTF-8 iCalendar 2.0, up to 100,000 bytes and 100 VEVENTs; folded lines are supported.
- Explicit `DTSTART;VALUE=DATE` and optional `DTEND;VALUE=DATE`. An absent end means one day. The end date is exclusive, as specified by [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.6.1).
- Cancelled and transparent events are skipped. Other events, including tentative ones, block dates.
- Only the next 365 local calendar days are imported. Entirely outside events are skipped; partially outside events are clipped. The preview reports these counts.
- Overlapping, adjacent and duplicate input ranges are merged before checking availability.

The whole file is rejected for malformed dates, recurrence/exception rules, timed events, DURATION, scheduling methods other than PUBLISH, or additional components such as VTIMEZONE/VALARM. This deliberately limited first version does not guess time zones or expand recurring bookings. Export a date-only occupancy calendar from the source system. Event names, descriptions, guest details and source URLs are not stored or returned; block reasons are simply `iCal import`.

## API and operations

Authenticated owner/admin endpoints accept JSON `{ "content": "BEGIN:VCALENDAR..." }`:

- `POST /owner/properties/{id}/occupancy-import/preview`
- `POST /owner/properties/{id}/occupancy-import`

Responses contain date ranges with `ready`, `existing` or `conflict` status, skipped/clipped counts, `applied` and `created`. A conflict result is HTTP 200 with `applied: false`; callers must inspect it. Invalid files return 400/422, unauthorized access 401/403. Demo mode rejects confirmation. No new migration or dependency is required.

This is an additive manual snapshot import, not a connection to a source calendar. Reimporting changed or cancelled events does not remove previous blocks; review/remove those explicitly. If you remove a block and import the file again, it can be created again. Imported occupancy is included in outbound exports, so avoid feeding a Bookica export back into the same apartment. No external URLs are fetched. Automatic refresh, source-aware reconciliation, last-sync reporting and broader format support remain future work.
