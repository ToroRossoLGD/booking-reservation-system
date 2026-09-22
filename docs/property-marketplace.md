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

Property photographs, property favorites, map filters, sales inquiries,
moderation and property-specific detail URLs are future work. The current cards
use clearly labeled illustrations. Existing resource favorites are unchanged.

Short stays may use direct owner contact or opt in to fixed-price nightly
booking with payment at the property. Seasonal pricing and online checkout
are not included yet; see the nightly booking guide.

## Validation

The property tests cover repository filtering/pagination in an isolated SQLite
database, create/edit/publication permissions, draft privacy, request validation
and migration upgrade/downgrade. Existing backend tests remain part of the full
suite. Browser tests use deterministic API fixtures for public search, contact,
mobile layout and the existing login flow; frontend component tests cover
owner publication and withdrawal. CI applies migrations against PostgreSQL.
