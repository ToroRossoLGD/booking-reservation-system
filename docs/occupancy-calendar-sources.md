# Reconcile a named calendar source

Open **Uvoz po izvoru kalendara** in the short-stay availability panel. Create a descriptive source name (not a private URL), then select it each time you import that source's complete calendar, either from a file or through the existing URL download flow. An apartment can have up to 10 sources, shared across all listing aliases.

Preview shows the desired ranges and the exact old source ranges proposed for removal. Confirmation retains unchanged blocks, adds new ones and deactivates blocks belonging to that source which are missing from the snapshot. A valid empty calendar therefore proposes removing all active blocks of that source; it still requires explicit confirmation. This includes old source blocks outside the current 365-day import window.

Rerun preview if the source has changed since your previous preview. The server checks the source revision under the same apartment lock used by bookings and confirms changes atomically. A conflict with a reservation (including preparation time), a manual block or another source leaves all previous source blocks unchanged. Even an identical block belonging to another source/manual import is a conflict: it is never silently adopted.

**Bez izvora — samo dodaj blokade** retains the previous additive behavior. Existing manual imports are not assigned to a source automatically. Source ownership is attached to newly created blocks, independent of their display reason. Manual deletion of a source block is permitted; the next source import can recreate it if the date still appears in the snapshot. Imported source blocks are included in outgoing occupancy calendars, so avoid circular imports.

Each source displays its latest confirmed attempt, success/conflict outcome and latest successful import time in UTC. Previews, invalid input and stale confirmations do not update these timestamps. A conflict updates the attempt time but preserves the previous success time. Existing import history continues to record additions/conflicts; detailed removal ranges are shown in the immediate preview/result, not retained as an audit log.

**Ukloni izvor i njegove blokade** requires a separate confirmation, removes the source definition and deactivates only its active blocks. Reservations, manual blocks and other sources remain. Source names can be reused after removal; a recreated source has a new identity.

## API and deployment

The selected source also shows a manual-import freshness indicator. A conflicting latest attempt takes precedence; otherwise it distinguishes no successful import, a success within 24 hours and an import at least 24 hours old. The 24-hour threshold is a review reminder, not a guarantee that the provider's occupancy is current. While visible, the indicator updates every minute and when the window regains focus. It uses the browser clock and the last loaded source status; **Osveži izvore** reloads server status. No background download or new migration is introduced by this indicator.

- `GET /owner/properties/{id}/occupancy-sources`: owner/admin source list, private/no-store.
- `POST /owner/properties/{id}/occupancy-sources`: `{ "name": "Channel A" }`; an identical name returns the existing source for safe retries.
- `DELETE /owner/properties/{id}/occupancy-sources/{source_id}`: remove source and deactivate its blocks.
- Existing import preview accepts optional `source_id`; its response includes `source_revision`, `removed` and `removed_ranges`.
- Confirmation sends both `source_id` and the preview's `source_revision`. A missing/stale revision returns 409; obtain a new preview. If a response was lost, inspect the source status and preview again rather than assuming the confirmation failed.

Run `alembic upgrade head` before deployment (migration `d05f26ab1934`). It adds source definitions and a block ownership association; existing blocks remain unassigned. Demo mode disables source creation/removal and import confirmation.

Manual reconciliation continues to work without a saved link. Sources can now optionally use [automatic refresh](automatic-calendar-refresh.md), with encrypted provider URLs, explicit opt-in and separate connection health. Always supply a complete calendar for the selected source; never substitute a partial or unrelated snapshot.
