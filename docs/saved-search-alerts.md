# Saved-search alerts

Signed-in users can enable or disable in-app notifications separately for each
account search in **Pretrage na nalogu**. Saving, renaming or transferring a local
search never opts the user in automatically. Alerts appear in the existing
notification inbox with a link to the property; dated stay searches retain their
dates and guest count. Email and push delivery are not included.

`PATCH /saved-searches/{id}/alerts` accepts `{"enabled": true}` or `false` and
returns the updated search. Authentication and ownership are required (another
user's ID returns 404). Repeating an enable request preserves its start time.
Disabling stops future processing; already delivered notifications remain in
the inbox. Re-enabling starts from the new opt-in time, without catching up on
publications made while disabled. Deleting a search removes its processing
history through database cascades.

Only a property's first publication recorded after opt-in is eligible. Drafts
are ignored until published. Existing published properties are timestamped by
the migration and are not backfilled for later opt-ins. Historical publication
dates for currently withdrawn listings were not previously stored, so their
first publication after this upgrade is treated as new.

The worker uses the same search filters as the marketplace, including offer,
city, amenities, price, seasonal rates, dates, guest capacity and booking rules.
Matching uses the current listing and availability when processed, not a frozen
publication snapshot. Owners do not receive alerts for their own listings.
Later edits or republication do not send another alert. Availability can change
after delivery and must be checked on the listing. One property can produce one
notification for each of several matching searches.

## Deployment and operation

Run `alembic upgrade head` (revision `ebc79532468f`) before restarting the API,
Celery worker and Celery Beat. Existing Redis/Celery services in Docker Compose
are sufficient; no new provider credentials are required. Beat schedules
`send_saved_search_alerts_task` every 60 seconds. Each run handles up to 25
searches and 50 unprocessed publications per search. Backlogs can take several
minutes, and no delivery occurs while the worker or Beat is stopped.

Processing locks the user and search in the same order as preference changes.
Notification creation and the `(search_id, property_id)` processing record
commit together. Concurrent workers skip busy users; retries and deleted inbox
notifications cannot create duplicate alerts. Non-matching publications are
also recorded, so later edits do not turn them into fresh announcements.
The worker queries unprocessed publications rather than advancing an ID cursor,
so a late-committed lower ID is still eligible. Processing history is retained
until the search or property is deleted; monitor its size as usage grows.
