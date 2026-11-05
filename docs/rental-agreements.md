# Long-term rental agreements and payment records

This P2 slice connects an existing long-term rental inquiry to a shared agreement record and a monthly payment plan. Open **Dogovor o najmu i kirije** on `/owner/rentals` or `/rentals`.

## Workflow

1. The inquiry owner proposes a start date, duration (1–120 months), monthly rent, optional deposit and notes. The inquiry must be active and its property must still be a long-term listing owned by that owner.
2. The tenant reviews the exact terms and explicitly confirms acceptance or rejection. The owner can withdraw a pending proposal. Rejected or withdrawn proposals remain readable, and the owner can submit a replacement.
3. Acceptance creates all monthly charges and a separate deposit charge atomically. Both participants can read the plan; only the original owner can mark a whole charge paid or remove that mark. Each change requires confirmation and records a timestamped audit event.
4. The other participant receives an in-app notification. Existing optional email digests can include these notifications; this feature does not send payment reminders.

## Dates and amounts

Dates use the property's timezone, captured when the proposal is created. A proposal cannot start in the past, and acceptance rechecks its start date. The end date is exclusive. Each monthly due date is anchored to the original start day, clamped to the last day of a shorter month: January 31 → February 28 → March 31. The deposit is due on the start date; a zero deposit creates no deposit charge.

Money uses integer minor units, with currency copied from the inquiry. Utilities are excluded. The displayed outstanding total includes future charges and the deposit, excluding charges voided by an agreed early end; it is not an overdue balance. An overdue label only means that the due date passed without an owner-recorded payment.

## Mutual early end

Open **Prevremeni završetak najma** inside an accepted agreement. The original owner selects a monthly boundary and supplies a reason, reviews the affected charges, then sends the proposal. The original tenant explicitly accepts or declines; the owner can withdraw a pending proposal. A proposal alone changes neither the agreement nor its charges. Both participants can read the paginated history, notes and decision timestamps.

Supported end dates are the start of the second or a later rent period, before the original exclusive end date, and no earlier than today in the captured property timezone. For a January 31 three-month agreement, February 28 and March 31 are valid boundaries; February 15 is not. One-month agreements have no earlier monthly boundary. This first version does not prorate a partial month or cancel the entire initial period.

Acceptance is atomic: it records `terminated_on`, increments the agreement version and marks rent charges due on or after that date with `voided_at`, incrementing their versions. Original dates, amounts, notes, charges and payment audit events remain stored. The deposit and earlier rent retain their payment controls. Voided charges remain visible, cannot receive payment changes and are excluded from the outstanding total. New rental agreements can begin on the agreed exclusive end date; overlap checks still protect the retained period. Nightly reservation availability is unaffected.

Any owner-recorded payment on an affected future rent charge blocks both proposal creation and acceptance. This is rechecked under the same locks used by payment updates, so a concurrent payment and conflicting termination cannot both succeed. There is no automatic refund: participants must resolve any actual transfer separately, and an incorrect payment mark can be corrected through the existing audited payment controls. A pending proposal whose date has passed can be withdrawn or declined and replaced.

Only one pending or accepted early-end proposal is allowed per agreement. Request UUIDs are scoped to that agreement; identical submissions return the existing proposal, while changed terms conflict. Decisions require the current proposal version. Writes require verified email, share the rental-agreement rate budget and are disabled in demo mode. Original participant permissions continue after the source inquiry closes or ownership changes, matching payment-record access. Acceptance cannot be reversed or shortened again through this workflow.

The UI requires a confirmation step for submission and decisions, offers explicit refresh after failures, and refreshes the agreement and payment plan after acceptance. Both participants receive the relevant counterparty notification. This is a shared operational record; it does not create an electronic signature or generate lease paperwork.

## Access and consistency

- Only the original inquiry participants can read agreement terms, charges and audit history. Responses are private and not cacheable. Account changes clear the open frontend panel.
- Writes require verified email, are rate limited, and are disabled in demo mode.
- Proposal request UUIDs are scoped to the owner. An identical retry returns the existing proposal; reusing the UUID for different terms returns a conflict.
- Version checks reject stale decisions and payment changes. After an uncertain or failed write the UI requires a refresh before another attempt.
- Database locks serialize acceptance for the same venue, including listings sharing that venue. Accepted rental agreements cannot overlap; adjacent exclusive-end intervals are allowed.
- A pending proposal cannot be accepted after the inquiry is closed/withdrawn or the property changes owner. Accepted records remain available to the original participants, including after an ownership change; no automatic rights transfer occurs.
- Lists show ten proposals per page. Charge history displays the latest twenty changes; older audit events remain stored.

## Scope still open

This is a shared record of terms and manual payments, not electronic signing, generated lease paperwork, bank confirmation or online collection. It does **not** block nightly reservations or synchronize external calendars. Owners must manage that availability separately.

Original accepted terms are retained, with a separately recorded mutual early end where applicable. General amendments, partial-month termination, recurring collection, partial payments, refunds and deposit returns are not implemented. There can be only one proposed or accepted agreement per inquiry, including after an early end; a later renewal needs another inquiry. These limits keep the broader **Long-term leases and monthly rental payments** roadmap item open.

## Deployment and validation

Run `alembic upgrade head` before deploying the API. Migration `e72a93bc8601` follows `d61f82ab7590` and adds agreements, charges and payment audit tables; it does not modify existing inquiry data. Downgrading removes those new records.

Migration `f83ba4cd9712` adds nullable early-end/void timestamps and the termination history table. Existing agreements and payments retain their values. Its downgrade removes termination history and void markers; do not deploy the old application against agreements that rely on those markers without a data-recovery plan.

Backend tests cover authorization, verified writes, idempotency, state/version conflicts, date anchoring, rollback, migration round-trip and PostgreSQL concurrent acceptance/payment updates (`STAY_TEST_POSTGRES=1`). Frontend tests cover explicit confirmations, request amounts, account changes, conflict recovery and audit display. Playwright exercises proposal → acceptance → manual payment on desktop and mobile with mocked APIs.

Early-end tests also cover retained deposits and paid history, invalid/expired boundaries, declined/withdrawn proposals, releasing only the shortened interval, transaction rollback, preserving existing migration data and concurrent payment versus termination. Browser scenarios exercise owner proposal → tenant confirmation → voided plan/history on desktop and mobile.
