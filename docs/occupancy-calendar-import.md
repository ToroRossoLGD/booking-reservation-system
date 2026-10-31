# Import an occupancy snapshot

Owners and administrators can select an `.ics` file in a short-stay listing's availability panel, choose **Pregledaj uvoz**, review the dates and choose **Potvrdi uvoz blokada**. Preview never writes data. Confirmation checks current availability again while holding the apartment lock shared by booking creation. If any range conflicts, no ranges are written and the response identifies the conflicting dates.

Imported dates become ordinary private blocks shared across all listings of the apartment, and immediately affect availability, search and new bookings. Remove them individually in the existing block list. Existing reservations and blocks are never overwritten or cancelled. An exact active block is reported as already present, making an immediate retry safe from duplicate blocks. An overlapping block with different boundaries is a conflict. Reservation preparation gaps also count as occupied.

## Supported files

Conflicting preview/confirmation ranges now include `conflicts`: occupied `check_in`/`check_out` dates and `kind` (`reservation` or `block`). Reservation ranges include preparation gaps, so the UI labels them as reservation/preparation rather than claiming these are the guest's stay dates. End dates remain exclusive. Only date/type metadata is returned; no guest details, private block reasons or provider links are exposed. Exact existing blocks accepted by additive import and the selected source's own blocks are not reported as conflicts. Details are recomputed at confirmation and are not persisted in import history.

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

Responses contain date ranges with `ready`, `existing` or `conflict` status, skipped/clipped counts, `applied` and `created`. A conflict result is HTTP 200 with `applied: false`; callers must inspect it. Invalid files return 400/422, unauthorized access 401/403. Demo mode rejects confirmation.

## Import history

Choose **Istorija uvoza kalendara** to see the latest 10 confirmed attempts for the apartment, newest first. All listing aliases share this history. Each entry shows its time in UTC, success or conflict outcome, new/existing blocks, conflicting ranges and skipped/clipped event counts. A successful attempt with no new blocks is labeled separately. Refresh the history after an uncertain network response to check whether an attempt committed; retrying a confirmation can add another history entry even when no duplicate blocks are created.

`GET /owner/properties/{id}/occupancy-import/history` returns these entries to the current owner or an administrator, with private/no-store caching. The UI refreshes an open history after confirmation and clears it on an account change. History survives page reloads. It does not contain file contents, guest metadata, source URLs or filenames. Records describe the outcome at import time; later removal of a block does not rewrite history.

History is stored atomically with newly imported blocks. Conflict attempts record an outcome without adding blocks. Preview-only requests, malformed/unsupported files, authorization failures and rolled-back transactions are not recorded. Earlier imports are not backfilled. The endpoint shows only the newest 10 records; older records remain in the database. History includes manual and automatic applied/conflicting imports; download failures are shown in the automatic refresh panel instead.

Before deploying history support, run `alembic upgrade head` (migration `c94e15fa0823`). No new dependency is required.

Without a selected source, this is an additive manual snapshot import. Reimporting changed or cancelled events does not remove previous blocks; review/remove those explicitly. [Named calendar sources](occupancy-calendar-sources.md) support previewed removal/replacement of their own blocks. If you remove a block and import the file again, it can be created again. Imported occupancy is included in outbound exports, so avoid feeding a Bookica export back into the same apartment. The separate [URL import flow](occupancy-url-import.md) can fetch a snapshot from an approved provider. Optional [automatic refresh](automatic-calendar-refresh.md) supports encrypted saved connections, scheduling and connection health. Broader format support remains future work.
