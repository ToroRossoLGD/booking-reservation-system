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
Filters are local to the page and are not persisted across a reload.

No migration or new environment variables are required.
