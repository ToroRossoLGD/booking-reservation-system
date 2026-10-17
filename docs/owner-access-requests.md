# Owner access requests and administrator approval

Verified customers can request the owner role at `/owner-access`. Public signup
still creates only customers; neither request input nor public registration accepts
a role override. Administrators review requests at `/admin/owner-access` and must
enter a user-visible reason, then explicitly confirm approval or rejection.

## Rules and security

- A request contains 20–2000 trimmed characters explaining planned listings and
  authority to manage them. Do not collect identity documents or payment details
  here. Administrators must verify authority through their trusted process before
  approving; this feature is not automated identity/property verification.
- One pending request per account. Submissions lock the user row; a partial unique
  index independently enforces the pending limit. UUID retries with identical
  contents return the same record; reused UUIDs with changed contents conflict.
- After a terminal decision, a fresh submission is allowed no earlier than 24 hours
  after the previous submission. Owner/admin accounts cannot request privileges.
- Production uses the existing shared Redis limiter: 20 requests per IP and 3 per
  account per hour, keyed separately from property reports. Reads remain available.
- Only administrators can list all requests or decide. Customers see only their own
  records. Decisions record reviewer ID, time, outcome and explanation; reviewer ID
  is not exposed in the response. Terminal decisions cannot be edited by this API.
- Approval rechecks the locked applicant's current customer role, verified email and
  unchanged email snapshot. A changed account causes 409 instead of overwriting its
  role. Self-decisions are prohibited. Admin creation/demotion still uses trusted
  operator provisioning, not this API.
- Role change, token-version increment, active API-key revocation, decision and
  in-app notification commit atomically. The approved user signs in again. Requests
  already in flight cannot be retroactively cancelled. Rejection leaves credentials
  and role unchanged. Identical retries from the original reviewer are idempotent;
  conflicting decisions return 409.
- Demo mode rejects submissions and decisions. No email/push delivery is added;
  decision notifications appear in the existing private inbox after login.

The audit records are database-backed, not tamper-proof against database operators.
Do not delete history as a routine rollback: it records granted privileges.

## Deployment

Apply `alembic upgrade head` before releasing the API/frontend. Migration
`a79b46c120de` adds only `owner_access_requests`; existing user roles remain unchanged.
The new table references users, stores request/decision text and retains history.
The existing Redis configuration is reused; no new environment variables.

Downgrade removes request history and does **not** undo previously granted roles or
restore sessions/API keys. Prefer application rollback while preserving the table.
If a role must be removed, use the operator provisioning procedure with the current
expected role and retain the incident record. Back up audit data before schema rollback.

Routes:

| Method | Path | Scope |
| --- | --- | --- |
| GET | `/owner-access/mine?offset=0` | Authenticated account's history, 20 per page |
| POST | `/owner-access/requests` | Verified customer, UUID and details |
| GET | `/admin/owner-access?status=pending&offset=0` | Admin queue, pending/approved/rejected |
| POST | `/admin/owner-access/{id}/decision` | Admin, approved/rejected and note |

## Validation and remaining launch work

Tests cover privacy/roles, verification, demo mode, UUID retries, duplicate requests,
rejection/resubmission, changed-account conflicts, transaction rollback, notification
deduplication, real HTTP bearer revocation and PostgreSQL simultaneous submissions
and decisions. PostgreSQL tests use a unique temporary schema and run under existing
`STAY_TEST_POSTGRES=1` CI configuration. Browser tests exercise desktop/mobile user
and administrator flows, errors, confirmation, history and re-login guidance.

This implements the P1 owner request/approval workflow. It does not complete the
whole onboarding/policies milestone: named operational reviewers, real-world owner
verification procedures, response expectations, legal/privacy wording, retention
and deletion policy, and private HTTPS acceptance still require project decisions.
