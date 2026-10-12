# Support ticket and message budgets

Support writes now join the shared legacy write limiter. Existing integration
budgets keep their Redis key format and expiry; moving the implementation to
`app/core/legacy_write_rate_limit.py` does not reset those counters.

| Operation | Per IP | Per authenticated author | Window |
| --- | ---: | ---: | --- |
| `POST /support/tickets` | 30 | 5 | 15 minutes |
| `POST /support/tickets/{id}/messages` | 120 | 30 | 60 seconds |
| `POST /support/admin/tickets/{id}/messages` | Shares message budget | Shares message budget | 60 seconds |

The message budget spans all tickets and both message endpoints, including
administrator internal notes. It is per author, not per ticket or recipient, so
one customer's activity does not spend the administrator's account allowance.
Creating a ticket has a separate allowance. Administrators are not exempt; tune
the initial values against support workload before launch.

IP checks run before body parsing/authentication and use the trusted ASGI client
address. Account checks use the authenticated user ID, so different bearer tokens
or API keys for the same user cannot reset the budget. Changing ticket IDs also
does not reset it. Account checks precede business logic; malformed/unauthorized
attempts that reach them count. Ownership, admin role, ticket state, message length
and internal-note visibility checks still apply.

Redis stores HMAC identities and atomic expiring counters, never ticket bodies or
plaintext user/IP identities. Exhaustion returns 429 with `Retry-After`, no-store
and a request ID; allowed origins can read retry metadata. Redis failure returns
redacted 503 with a 30-second suggested retry. Production always enforces these
limits; development/test opts in with `AUTH_RATE_LIMIT_ENABLED`.

GET history/list/detail, customer ticket closure and admin status/assignment
updates do not consume these budgets. Their existing authentication/authorization
still applies. Limiter failure does not block those operations, though unrelated
database or service failures can. This PR adds API protection, not a new support
frontend or automatic retries.

Unit/API tests cover every new path, shared message budgets, normalization,
authorization, 429 metadata, pre-parsing rejection, Redis failure and closure
during an outage. Real-stack smoke exercises exhausted ticket/message budgets
without creating tickets, preserves ticket budgets through API/Redis recreation,
and checks reads/closure remain reachable. Existing real-Redis tests cover the
shared atomic counter and expiry behavior.

NAT users share IP limits. Fixed windows allow bursts at expiry; Redis data loss
or JWT-secret rotation can reset counters. Do not flush shared Redis to unblock a
user. Private staging still requires actual-client topology and workload tuning.
Reservation/payment/media legacy limits and the other P1 acceptance tasks remain
open. No database migration or new environment variable is needed.
