# Nightly arrival and departure times

Owners can set **Prijava od** and **Odjava do** when editing a **Stan na dan** listing. Both fields use local `HH:mm` time in the listing's IANA timezone. Provide both or leave both empty for an arrangement with the host. New listing forms suggest 14:00 and 11:00; existing listings are not assigned invented rules.

Long-term rental and sale forms do not show these fields. Switching to either offer type clears them, and the API rejects non-null times on those offers. Checkout can be earlier in the day than check-in because they occur on separate dates.

Times appear in listing actions (including listings without online booking), the server quote, confirmation, and guest/owner reservation lists. Each new reservation snapshots the times and timezone. Later listing changes do not change existing reservations or idempotent retries. Calendar downloads remain all-day stays with the agreed local times in the description.

The booking UI submits `expected_check_in_time`, `expected_check_out_time`, and `expected_timezone` from its quote. A mismatch returns 409 and requires a new quote. These request fields remain optional for compatibility with older API clients; supplied fields are checked even when explicitly null. Availability, nightly pricing, and cancellation deadlines remain date-based.

## Deployment

Run `alembic upgrade head` before deploying the application. Migration `f61c8a213574` adds nullable time columns to `property_listings` and `stays`. Existing records retain null; the UI tells guests to arrange times with the host. Downgrading removes the stored times while preserving listings and reservations.
