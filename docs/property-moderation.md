# Property reports and moderation

Signed-in visitors can report a public nightly, rental or sale listing from its
detail page. Categories cover misleading information, suspected fraud,
inappropriate content, duplicates and other problems. Reports require a short
description; owners cannot report their own listings. Submission does not
automatically hide the property.

## User interfaces

`/moderation` shows the user's own reports. Owners also see decisions on their
properties, and administrators get report queues and listing moderation cases.
Queues have pagination; admins filter reports by outcome and cases by state.
The owner panel and moderation notifications link to this page.

Administrators can inspect the property's current private preview and the
title, description, city, offer and price snapshot captured when reported.
They can dismiss the report or suspend the listing, giving an explanation.
The snapshot does not archive image files or external pages.

Suspension sets `is_published=false`. Existing public detail, search, favorites,
booking, rental inquiry and saved-search-alert flows therefore stop offering
the listing. A database check also prevents any suspended/appealed listing from
being published. Existing stays, prices, calendar occupancy and private
conversations are preserved; suspension does not cancel a booking or refund a
payment. Previously downloaded/cached public media is not revoked.

Owners can edit suspended listings as drafts and request another review with
an explanation. They cannot move a suspended listing to another venue or
republish it. Administrators may uphold the suspension or restore publishing
permission. **Restoration leaves the listing unpublished**: the owner explicitly
checks and publishes the draft. This controls one listing, not all aliases or
the owner's account.

## Privacy and integrity

- Report text and snapshots are visible only to the reporter and administrators.
  Owners receive moderator explanations and their own appeal history, not the
  reporter's identity or original report text. Administrators should not copy
  personal information into owner-visible explanations.
- Decisions and appeals retain an event history with actor, time, action,
  explanation and revision. Reporter responses redact moderator notes/appeals;
  public listing responses contain no moderation fields.
- One open report per user/listing and at most 20 open reports per user limit
  accidental duplicates. Request UUIDs make identical retries safe; different
  payloads using the same UUID return 409.
- Decisions require the listing's current moderation version. Concurrent or
  stale decisions cannot overwrite each other. Listing, report status, audit
  event and notifications commit together. Recipient key locks precede listing
  locks to avoid inversion with booking/report creation.
- Submitted appeals appear in the administrator queue. Reporter outcomes and
  owner decisions produce in-app notifications; email/push and an administrator
  broadcast are not included. Refresh queues to see new work.

## Endpoints and deployment

| Endpoint | Access/purpose |
| --- | --- |
| `POST /properties/{id}/reports` | Signed-in reporter; category, details, request_id |
| `GET /property-reports/mine` | Reporter's own history |
| `GET /admin/property-reports` | Admin queue; status filter |
| `POST /admin/properties/{id}/reports/{report_id}/decision` | Admin hide/dismiss |
| `GET /owner/property-moderation` | Current owner's cases |
| `GET /admin/property-moderation` | Admin cases; state filter |
| `GET /properties/{id}/moderation-history` | Owner/admin paginated history |
| `POST /properties/{id}/moderation` | Owner appeal or admin restore/uphold |

Decision bodies include `action`, `note`, `version` and `request_id`. List
endpoints accept `offset` and `limit` (default 20, maximum 100).

Run `alembic upgrade head` (revision `a1d917546801`) before deploying the API and
frontend. It follows the stay-date-change migration from PR #131, keeping one
migration head. Existing listings default to clear and keep publication state.
No new worker or provider is needed. Downgrade removes moderation metadata;
it does not automatically republish withdrawn listings.
