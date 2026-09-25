# Property search

The public catalog supports inclusive price and area ranges, exact room counts
(0 means a studio), and sorting. Public searches always exclude unpublished listings.
Changing filters restarts pagination. The owner catalog keeps its existing behavior.

`GET /properties` accepts these optional query parameters in addition to `city`,
`offer_type`, `limit` and `offset`:

| Parameter | Values |
| --- | --- |
| `min_price_cents`, `max_price_cents` | Integers from 0 to 1,000,000,000,000, in minor currency units |
| `currency` | EUR, RSD or USD |
| `min_area_sqm`, `max_area_sqm` | Integers from 1 to 100,000 |
| `rooms` | Exact integer count from 0 to 100 |
| `check_in`, `check_out`, `guests` | Optional availability group: ISO dates and 1–100 guests; requires `offer_type=short_stay` |
| `sort` | `newest` (default), `price_asc`, `price_desc`, `area_desc` |

Price ranges and price sorting require both `offer_type` and `currency`. There is
no currency conversion: only listings in that currency and offer type match.
Short-stay prices are per night, long-term prices per month, and sale prices total.
Invalid or reversed ranges return HTTP 422. Equal sort values use descending
listing ID as a stable tiebreaker. Newest means descending listing ID.
Pagination uses offsets, so listings published/edited between requests can shift pages.

Example: `/properties?offer_type=long_term&currency=EUR&min_price_cents=50000&max_price_cents=75000&rooms=0&sort=price_asc`

In the UI, enter prices in whole currency units with up to two decimal places.
Apply advanced filters explicitly. Switching offer type clears the price range
and price sort; area and rooms remain applied. Clear filters restores the catalog.
Applied filters and pagination are stored in the browser URL and restored on reload.

## Shareable searches

**Kopiraj link pretrage** copies the current applied search, including city,
offer type, currency, price/area ranges, room count, sorting, stay dates, guest
count and page offset. Unsaved input edits are not included until submitted.
If clipboard access fails, the page displays a selectable link instead.

Opening the URL restores the controls and requests fresh results. Back and
Forward restore previous searches and pages. Clearing filters restores `/`;
Back can recover the previous selection. Links do not store a snapshot of
listings or hold availability, and require no account.

Only supported query parameters are retained. Invalid values, reversed ranges,
unsupported enums and incomplete stay-date groups are ignored. Price filters
still require an offer type and currency. Offset is normalized to a 12-item
page boundary; unknown parameters and fragments are excluded from copied links.
The initial URL is normalized without adding a browser-history entry.

## Short-stay availability

Select **Stan na dan**, open **Napredni filteri i sortiranje**, and enter arrival,
departure and guest count. Supply all three fields together. A stay must be
1–90 nights; partial/invalid groups or other offer types return HTTP 422.
Clearing filters or switching offer type removes the availability selection.

Results include only published listings with online booking enabled, enough
guest capacity and a minimum-night rule satisfied by the requested stay.
Arrival must be tomorrow or later and departure within 365 days, in each
property's own timezone. Dates outside that window yield no matching listings.
Timezone eligibility and availability are applied before counting and pagination.

Confirmed stays block the whole venue, including its other listing aliases.
Cancelled stays do not block availability. Checkout is exclusive, so a new
guest can arrive on the previous guest's departure date. Filtering uses a
correlated SQL existence check and one timezone query, not a request per listing.

Example: `/properties?offer_type=short_stay&check_in=2030-10-04&check_out=2030-10-07&guests=3`
(Use future dates within the booking window when trying this example.)

Selected dates and guests prefill inline booking and are carried into the
listing-title link's query parameters. Reloading that link preserves the prefill.
Malformed query parameters are ignored. The page's copy-link button still
copies the property URL without dates. Prices and price filters remain per night,
not a total for the requested stay; request a quote to see the total.

Search is a snapshot, not a reservation or hold. The existing quote and
confirmation flow rechecks availability, price and booking rules; transaction
locks still protect against simultaneous overlapping reservations.

No migration or new environment variables are required.
