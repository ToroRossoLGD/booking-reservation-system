# Verified nightly property reviews

Guests can open **Oceni boravak / moja recenzija** on `/stays` after the checkout date has passed in the reservation's saved timezone. Only confirmed reservations qualify; cancelled stays, checkout-day stays and future stays do not. This verifies a past reservation, not payment or physical attendance.

A review contains an integer rating from 1 to 5 and a trimmed comment of 10–2000 characters. There is one review per stay. The stay row lock and unique database constraint protect against concurrent submissions. Retrying the exact same rating/comment returns the existing review; different content for the same stay returns 409. Reviews cannot be edited through this first version.

Visitors open **Prikaži recenzije gostiju** on a nightly listing or expanded card to see a paginated list, total count and average across all its reviews. Public responses contain only review ID, rating, comment and publication timestamp: no account ID, name, email, stay ID or stay dates. Comments render as text. Authors should keep personal information out of their public comments.

Reviews are associated with the booked listing, not automatically shared with other listings for the same venue. Unpublished listings and listings changed to sale/long-term rental do not expose public reviews. The guest can still read their own review from the original stay. Current venue owners cannot submit a new self-review.

## API

| Endpoint | Access |
| --- | --- |
| `GET /properties/{id}/reviews?offset=0&limit=10` | Public, published nightly listing; limit 1–50 |
| `GET /stays/{id}/review` | Reservation guest only; null if absent |
| `POST /stays/{id}/review` | Reservation guest after completion; body `{rating, comment}` |

Other users, including owners/admins, cannot create reviews on another guest's behalf. Existing hourly-resource reviews remain separate. Long-term rentals and sales do not get review submission without a completed transaction model. Owner replies, review editing/reporting and moderation UI are future extensions.

## Deployment and validation

Run `alembic upgrade head` before deployment. Migration `b83e0c435796` creates `property_reviews` with a unique stay reference and rating check. Downgrade removes reviews while preserving stays and listings.

Service tests cover eligibility, authorization, idempotency, privacy, aggregate pagination, input validation and migration round-trip. `STAY_TEST_POSTGRES=1` enables a concurrent retry test in an isolated PostgreSQL schema. Browser tests cover submission, reopening saved reviews, exclusion of cancelled/checkout-day stays and mobile public display.
