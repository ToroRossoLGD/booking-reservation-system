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
- Each inquiry has a private conversation. Both participants can send messages,
  see previous replies and viewing events, and check unread badges in their inbox.
- Open the conversation and use **Najnovije poruke / osveži** to fetch updates or
  **Starije poruke** for earlier history. Messages are displayed oldest first
  within each page of up to 50 messages.
- **Označi prikazane poruke kao pročitane** marks only the displayed incoming
  messages read. Older pages and messages arriving afterwards remain unread.
- Closed and withdrawn conversations remain readable but accept no new messages.
  This release uses manual refresh and does not send email/push notifications.

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
- `GET /rental-inquiries/{id}/messages?before_id=...&limit=50`: latest or earlier
  conversation page, including the caller's total unread count.
- `POST /rental-inquiries/{id}/messages`: `body` (1–3000 non-whitespace characters)
  and UUID `request_id`. Both participants can send messages.
- `POST /rental-inquiries/{id}/messages/read`: up to 50 `message_ids`; only incoming
  messages in the caller's inquiry are marked read.

Each update checks the participant, permitted action, lifecycle and version under
a row lock. Outsiders receive 404. Administrator status does not grant access to
other participants' private inquiries. Ownership is recorded at submission.
Existing participants retain access after a listing is unpublished.

Creation requires a UUID `request_id`. PostgreSQL account row locking serializes
retries; the same request returns the original inquiry, while changed payloads
with the same ID fail with 409. Only one active inquiry per account and listing is
allowed. The database also enforces uniqueness of `(user_id, request_id)`.

Conversation writes serialize on the inquiry row. Repeating a message request
returns the same message, including after the inquiry closes; reusing the ID
with different text returns 409. Ordinary messages do not change the inquiry
version, so a chat reply does not invalidate a pending viewing confirmation.
Viewing changes and their history entries commit together. Chat records are
append-only in the API; users cannot edit or delete the conversation history.

## Deployment and checks

Run `alembic upgrade head` before serving the new API. Migration `a19d72b6e430`
adds `rental_inquiries` after the nightly-stay migration. No existing rental or
nightly reservation records are converted. Downgrade removes inquiry records.

Migration `b27e4c8d9130` adds `rental_messages` and copies each existing inquiry's
opening message and latest saved owner reply. Earlier overwritten owner replies
cannot be recovered. The old reply timestamp was not stored, so it is displayed
without an invented date. Imported messages start unread for the recipient.
Downgrading this migration removes conversation history and read receipts while
preserving the existing inquiry records.

Backend coverage: `pytest tests/test_rental_inquiries.py`.
Conversation coverage: `pytest tests/test_rental_messages.py`; CI enables the
PostgreSQL concurrent-retry test with `STAY_TEST_POSTGRES=1`.
Frontend coverage: `npm test -- RentalInquiries.test.tsx`, plus `npm run build`
and `npm run lint` from `frontend`.
`RentalConversation.test.tsx` covers messages, retries, pagination and read
receipts; `e2e/rental-conversations.spec.ts` covers desktop/mobile conversation
flows with deterministic API fixtures.
