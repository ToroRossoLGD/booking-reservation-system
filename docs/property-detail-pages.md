# Property detail pages

Every published listing is available at `/properties/{id}`. Click its title in
the catalog or saved listings, or open the URL directly. The page fetches the
existing public `GET /properties/{id}` endpoint; login is not required to view it.
Withdrawn and missing listings return the same unavailable state. Invalid IDs
are rejected before an API request. Network errors offer a retry.

The page shows photos, description, room count, floor area and price with the
correct offer unit. It reuses the existing gallery, saved-listing control,
rental inquiry form and nightly booking form. Booking remains opt-in for short
stays; sale listings and short stays without booking use email contact.
Authentication and all booking/inquiry validations remain enforced by the API.

**Kopiraj link oglasa** copies the canonical URL without query parameters or
fragments. If clipboard access fails, a selectable address is displayed instead.
The browser title includes the listing title. This is a client-rendered page;
server-rendered social previews and per-listing Open Graph metadata are not included.

Production hosting must serve the frontend's `index.html` for
`/properties/{id}`, just as for `/saved` and `/rentals`. Vite already supports
this fallback. API requests continue through `/api`; no migration is required.

## Cleanup reviewed alongside this feature

- Removed unused `.ph-save` and `.ph-save[aria-pressed=true]` CSS rules left by
  an older save-button design. The active button uses `.property-save-button`.
- Removed unused `.ph-scene-home`; property cards use only `sea` or `city`.
- Extracted `PropertyActions` so inline cards and detail pages share one
  implementation of booking eligibility, rental inquiries and owner contact.

No stock React/Vite demo components or logo assets were found in the frontend.
The original `App`, `Dashboard`, hourly APIs and their tests are still connected
to active routes; they are not disposable boilerplate. Existing migrations and
Python package initializers are retained. This was a targeted review, not a
claim that every unused symbol in the repository has been eliminated.

Validation covers direct URL access and reload, invalid/missing listings,
clipboard fallback, saved-status failure, mobile layout, rental inquiries and
the full nightly quote/reservation/cancellation flow from both entry points.
