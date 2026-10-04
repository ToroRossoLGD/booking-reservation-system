# Sales inquiries and viewing appointments

Signed-in buyers can send a message (10–3000 characters) on a published sale listing. This applies to apartments and houses. The inquiry snapshots the title, total asking price, currency and seller. It has no move-in date, rental duration, deposit or monthly payment fields.

Buyers open `/sales`, and sellers open `/owner/sales` from the listing manager. Both inboxes are paginated and refreshable. A seller can reply or propose a future viewing in their local timezone; the API requires an explicit offset. The buyer accepts or declines the proposal, or withdraws the inquiry. Sellers may close it. Declining returns the inquiry to open so another time can be proposed.

Both participants can open the private conversation, send messages and mark displayed incoming messages as read. Opening, proposing, confirming, declining, closing and withdrawing create in-app notifications for the other participant. Ordinary chat messages use conversation unread counts. There is no email/push delivery or automatic reminder.

Confirmed viewings can be downloaded as `.ics`. Sales calendar identities are separate from rental identities, even when inquiry IDs match. The download is a one-time copy: later changes and cancellations must be updated manually in the external calendar.

## Integrity and privacy

- Only participants can read or change an inquiry; owner inboxes are scoped to the signed-in seller, including admin accounts.
- Only published sale listings accept new inquiries; buyers cannot inquire about their own property. Withdrawal or moderation suspension prevents new inquiries, but existing participants retain their conversation and can finish or close it.
- Each buyer can have one active inquiry per property. Once closed or withdrawn, a new inquiry is allowed. Other buyers can inquire independently.
- Creation and chat sends use request UUIDs bound to their payload. A retry returns the previous result; reusing the UUID with changed content is rejected.
- Viewing changes use an expected version. A stale update returns HTTP 409 and requires refreshing. Sending a chat message does not invalidate a pending viewing version.
- Price changes do not rewrite inquiry snapshots. Inquiry and message IDs belong to separate sales tables and cannot expose rental conversations with the same IDs.
- An inquiry or confirmed viewing does not block inventory, withdraw a listing, reserve a property, process an offer or create a purchase contract or payment.

## API

All endpoints require authentication:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/properties/{id}/sale-inquiries` | Create with `request_id` and `message` |
| GET | `/sale-inquiries/mine` | Buyer inbox (`offset`, `limit`) |
| GET | `/owner/sale-inquiries` | Seller inbox; owner/admin role |
| PATCH | `/sale-inquiries/{id}` | `version` and `action`: reply, propose, confirm, decline, close or withdraw |
| GET | `/sale-inquiries/{id}/messages` | History with `before_id` and `limit` |
| POST | `/sale-inquiries/{id}/messages` | Send `body` and `request_id` |
| POST | `/sale-inquiries/{id}/messages/read` | Mark incoming `message_ids` as read |

The frontend accesses these under `/api`. Proposals additionally require `owner_reply` and `viewing_at`; replies require `owner_reply`.

## Deployment and validation

Run `alembic upgrade head` before deploying the API, then deploy the frontend. Revision `b2ea28657912` creates `sale_inquiries` and `sale_messages`, with participant indexes, request uniqueness and a partial unique index for active inquiries. Existing rental data is unchanged. Downgrading removes sales history, so back it up before a rollback.

Backend tests cover participants, rental/sale isolation, snapshot prices, duplicate retries, stale updates, moderation visibility, unread history, rollback and migration round trips. PostgreSQL CI additionally checks concurrent creation and competing viewing updates. Frontend tests cover form retries, seller/buyer actions and calendar identities; browser tests exercise creation, viewing confirmation, read markers and withdrawal on desktop and mobile.
