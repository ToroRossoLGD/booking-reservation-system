# Seasonal nightly pricing

Owners edit seasonal periods inside the existing listing editor. Each period has
a first night, an exclusive end date, an optional label and a nightly amount in
the listing's currency. October 10–13 covers the nights starting on October 10,
11 and 12. Checkout does not consume another night's rate.

Up to 24 non-overlapping periods are supported per listing; adjacent periods are
allowed. Amounts must be positive and within the existing price limit. Rates may
be higher or lower than the base price. Outside the periods, the base price
applies. Dates refer to the property's local calendar, so daylight-saving
transitions do not change the number of billed nights. Switching the offer type
to rental or sale clears seasonal periods when the owner saves the form.

## Guest flow

1. Choose dates and guests. The quote includes a total and an expandable
   **Obračun po noćima** listing each night's amount.
2. Confirmation recalculates prices under the existing listing/venue locks.
   The frontend sends the expected total, currency and nightly breakdown. If any
   nightly amount changed, a new quote is required even if the sum is unchanged.
3. Guest and owner reservation lists display the saved breakdown. Later listing
   edits do not rewrite it; successful request retries return the original stay.

Quotes do not hold inventory or freeze a price. Existing availability, duration,
capacity, cancellation and pay-at-host rules still apply. No online payment is
added by this feature.

## Search prices

Without dates, filters and ordering use the base nightly price. Listings with
seasonal rates label it **Osnovna cena**. With dates, limits apply to the exact
average nightly amount: the database compares `total_cents` to `limit_cents *
nights`, avoiding rounding. Ordering uses the total and cards show **/ boravak**.
Filtering, counting and sorting precede pagination. SQLite and PostgreSQL use
equivalent seasonal-price expressions.

Example: two nights at EUR 100 and one at EUR 65 total EUR 265. An upper nightly
filter of EUR 88.33 excludes it, while EUR 88.34 includes it. Currency selection
still scopes comparisons; there is no currency conversion. Dedicated listing
pages show the labeled base price and obtain a final quote in the booking form.

## API and storage

- Listing writes/reads include `seasonal_rates`: an ordered array of
  `{start, end, price_cents, label}`, defaulting to empty. PUT remains a full
  replacement, including all seasonal periods.
- Date-filtered listing results include `stay_total_cents`; other reads leave it
  null. It is informational, not a booking guarantee.
- Quotes return `nightly_prices`: `{date, price_cents}` for each local night.
- Booking requests accept `expected_nightly_prices`. New clients should always
  return the quote's breakdown; older clients retain total/currency checks.
- Reservations save the server's calculation. The legacy `nightly_rate_cents`
  remains the saved base price; use `total_cents` and the array for seasonal stays.

Run `alembic upgrade head` before deployment. Migration `ad835198024b` adds JSON
seasonal rules with an empty default and nullable nightly breakdowns to stays.
Existing reservations retain their original totals/base prices, without a
fabricated breakdown. Historical prices are never recalculated.

Rates are per listing; occupancy remains shared by all listings of one venue.
Weekend recurrence, promotions, fees and seasonal minimum-night rules remain
separate future work.
