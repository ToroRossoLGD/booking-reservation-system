# Long-term rental inquiries

Published `long_term` listings now accept private inquiries from signed-in users.
The existing owner listing editor sets the monthly asking price. Open a listing's
details on `/` to send a desired move-in date, rental duration (1–120 months), and
message. The move-in date cannot precede today in the property's timezone.

## Workflow

- `/rentals`: the tenant's inquiries, owner replies, and viewing proposals.
- `/owner/rentals`: inquiries addressed to the signed-in owner.
- Owners reply and optionally propose a future viewing time and meeting place.
- Tenants accept or decline a proposal. Declining returns the inquiry to open so
  the owner can propose another time. A changed proposal needs a new acceptance.
- Tenants can withdraw; owners can close. These are terminal states. A new inquiry
  can then be sent for the same listing.
- Refresh the list to check for updates. This release displays the latest owner
  reply; it does not provide a threaded chat or email/push notifications.

Viewing times are submitted with a timezone offset and displayed in each user's
browser timezone. The form and viewing summary name that timezone explicitly.
Inquiries retain the title and monthly asking price at submission, even if the
listing changes. This price is informational, not a rental agreement.

An inquiry or confirmed viewing does **not** reserve the property, prevent other
people from inquiring, create a lease, or charge rent or a deposit. Lease signing,
monthly payments, and rental occupancy management are separate future work.

## API and access

- `POST /properties/{id}/rental-inquiries`: authenticated inquiry creation.
- `GET /rental-inquiries/mine`: paginated tenant inbox.
- `GET /owner/rental-inquiries`: paginated owner inbox; owner/admin role required.
- `PATCH /rental-inquiries/{id}`: `reply`, `propose`, `confirm`, `decline`, `close`,
  or `withdraw`, with the current `version`.

Each update checks the participant, permitted action, lifecycle and version under
a row lock. Outsiders receive 404. Administrator status does not grant access to
other participants' private inquiries. Ownership is recorded at submission.
Existing participants retain access after a listing is unpublished.

Creation requires a UUID `request_id`. PostgreSQL account row locking serializes
retries; the same request returns the original inquiry, while changed payloads
with the same ID fail with 409. Only one active inquiry per account and listing is
allowed. The database also enforces uniqueness of `(user_id, request_id)`.

## Deployment and checks

Run `alembic upgrade head` before serving the new API. Migration `a19d72b6e430`
adds `rental_inquiries` after the nightly-stay migration. No existing rental or
nightly reservation records are converted. Downgrade removes inquiry records.

Backend coverage: `pytest tests/test_rental_inquiries.py`.
Frontend coverage: `npm test -- RentalInquiries.test.tsx`, plus `npm run build`
and `npm run lint` from `frontend`.
