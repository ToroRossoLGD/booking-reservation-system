# Property details

Owners can record optional structured details when creating or editing a listing:

| Field | Values |
| --- | --- |
| `property_type` | `apartment`, `house` |
| `neighborhood` | Up to 100 characters |
| `floor` | Integer from -2 to 200; 0 means ground floor |
| `heating` | `district`, `electric`, `gas`, `heat_pump`, `solid_fuel`, `other` |
| `furnishing` | `furnished`, `partial`, `unfurnished` |
| `has_elevator`, `has_parking`, `has_terrace` | true, false, or null (not specified) |

These describe the property and work across sale, long-term rental, and nightly listings. They do not change rental inquiry, sale contact, or nightly booking rules. Existing listings have unknown values; nothing is inferred from descriptions. Empty form fields clear existing values on save. Owners should leave fields that do not apply unspecified.

Provided details appear on the dedicated listing page and expanded catalog/saved-listing cards. Unknown details are omitted; false is shown as **Ne**, not omitted. These are owner-provided descriptions, not independently verified claims.

## Search

Advanced filters accept the same field names. Neighborhood uses case-insensitive substring matching with literal `%` and `_`; all other details use exact matches. A true or false filter excludes unknown values. Filters apply before result counts and pagination, combine with existing city/offer/price/date filters, survive offer changes and reload, and are included in shared search URLs. Clear filters to remove them.

## Deployment

Run `alembic upgrade head` before deploying the API/frontend. Migration `a72d9b324685` adds eight nullable columns to `property_listings`; historical data remains intact with null details. Downgrading removes these details while preserving listings.

Listing updates retain the existing full-replacement PUT contract: omitted optional details are cleared. Deploy the current frontend alongside the API so edits include all fields.
