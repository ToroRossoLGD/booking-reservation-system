# Property marketplace: first working slice

Nightly booking is now available as an opt-in feature. See
[nightly apartment reservations](nightly-stays.md) for activation, date rules,
payment-at-property terms and deployment requirements. The contact-only path
below remains the default for existing listings.

The `/` home page now displays published property listings from the API instead
of demonstration data. Existing hourly reservations remain at `/booking` and
retain their account, payment, availability and owner workflows.

## Deploying

Run `alembic upgrade head` before deploying the new API/frontend. Revision
`c4e9a2b7d610` adds `property_listings`; it does not convert or rewrite existing
venues, resources or reservations. The catalog starts empty. There is no demo
data fallback when the API is unavailable.

## Publishing a listing

1. Sign in with an existing owner account and open `/owner`.
2. Create a venue using **Add venue** if you do not have one yet.
3. Under **Tvoji oglasi**, choose **Novi oglas** and select your venue.
4. Enter the title, description, city, floor area, room count, price and public
   contact email. Zero rooms denotes a studio.
5. Save a draft, or check **Objavi oglas** to show it on the public home page.
6. Use **Izmeni** to change the listing or uncheck publication to withdraw it.

The public contact email is deliberately entered by the owner; it is not copied
from their account. The contact link opens the visitor's email application.
Long-term rental listings also accept private inquiries and viewing proposals inside
the application; see [long-term rentals](long-term-rentals.md). Email notifications
are not sent for these inquiries.

## Price semantics

| Offer | API value | Displayed price |
| --- | --- | --- |
| Short stay | `short_stay` | Per night |
| Long-term rental | `long_term` | Per month |
| Sale | `sale` | Total asking price |

Prices are stored as integer minor units, with EUR, RSD and USD supported.
They are asking prices, not reservation quotes. A property listing references
an existing venue, not an hourly resource. No hourly rate is automatically
converted into a nightly rate and no existing resource becomes a property ad.
Deleting its parent venue also removes its listings through the foreign key.

## API

- `GET /properties?city=...&offer_type=sale&limit=12&offset=0`: published listings,
  newest first, case-insensitive city substring search and pagination.
- `GET /properties/{id}`: published listing, otherwise 404.
- `GET /owner/properties`: the signed-in owner's listings including drafts.
- `POST /properties`: create a listing for an owned venue.
- `PUT /properties/{id}`: replace all editable fields, including publication.

Writes require an owner/admin role. Owners cannot edit another owner's listing
or move a listing to someone else's venue. Admins may explicitly edit listings
across owners; their owner catalog still shows their own venues' listings.

## Deliberately deferred

Property photographs, map filters, sales inquiries,
moderation and property-specific detail URLs are future work. The current cards
use clearly labeled illustrations. Existing resource favorites are unchanged.

Short stays may use direct owner contact or opt in to fixed-price nightly
booking with payment at the property. Seasonal pricing and online checkout
are not included yet; see the nightly booking guide.

## Saved properties

Signed-in users can save any published listing with **Sačuvaj oglas**, revisit it
at `/saved`, and remove it from either the catalog or their saved list. Saved
cards retain listing details, nightly booking and long-term inquiry forms.
The list is private, paginated (12 cards per page in the UI), and ordered by the
most recent save. Repeating a save does not duplicate or reorder it.

The saved list shows current listing prices, not a price snapshot or reservation.
Unpublished listings disappear from the list and its count without exposing draft
details. They reappear when the owner republishes them. Deleted listings remove
their saved references through a cascading foreign key. Removing a saved listing
is idempotent and affects only the signed-in user's list.

- `GET /favorites/properties?offset=0&limit=12`: published saved listings.
- `GET /favorites/properties/status?property_ids=1&property_ids=2`: saved IDs from
  a batch of up to 50 visible listing IDs. The storefront makes one status request
  per results page, and remains usable if that request fails.
- `PUT /favorites/properties/{id}`: save a published listing; requires sign-in.
- `DELETE /favorites/properties/{id}`: remove the user's saved reference (204),
  even if the listing has since been unpublished or removed.

All four endpoints require authentication and determine the user from their
session. No caller-supplied owner/user ID is accepted. The original hourly
resource favorites remain separate. Migration `c38f5d9e0241` adds
`favorite_properties`; apply it with `alembic upgrade head` before deployment.
Downgrading this migration removes saved property records only.

Tests: `tests/test_favorite_properties.py`, `frontend/src/SavedProperties.test.tsx`
and `frontend/e2e/saved-properties.spec.ts`. PostgreSQL concurrent-save coverage
runs in CI with `STAY_TEST_POSTGRES=1`.

## Validation

The property tests cover repository filtering/pagination in an isolated SQLite
database, create/edit/publication permissions, draft privacy, request validation
and migration upgrade/downgrade. Existing backend tests remain part of the full
suite. Browser tests use deterministic API fixtures for public search, contact,
mobile layout and the existing login flow; frontend component tests cover
owner publication and withdrawal. CI applies migrations against PostgreSQL.
