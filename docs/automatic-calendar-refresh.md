# Automatic calendar refresh

Select a named calendar source and open **Podesi automatsko osvežavanje**. Enter an approved provider's complete date-only iCal URL and explicitly confirm **Poveži i uključi automatiku**. This authorizes background additions and removals of that source's blocks. Existing reservations, other sources and manual blocks remain protected by the same atomic conflict checks used for manual imports.

The connection queues its first refresh immediately, then approximately hourly. **Zakaži osvežavanje sada** queues a job; it does not perform an inline download. **Pauziraj automatiku** stops future applications, **Nastavi automatiku** queues another attempt, and **Ukloni sačuvani link** deletes the encrypted connection while preserving existing blocks. Removing the source itself also removes the connection and deactivates its source blocks, as before.

By default, a snapshot with no importable ranges is blocked if it would remove existing source blocks. Owners can explicitly enable empty-snapshot removal when connecting/replacing the link. This guard does not detect every incomplete provider export: only connect complete occupancy calendars. The existing parser still accepts only date-only, non-recurring events (100 events / 100,000 bytes); see [supported import formats](occupancy-calendar-import.md).

## Operator setup

1. Apply `alembic upgrade head` (revision `e16a37bc2045`).
2. Set exact provider hosts in `OCCUPANCY_IMPORT_ALLOWED_HOSTS`.
3. Generate a dedicated Fernet key using `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Store it securely as `OCCUPANCY_SYNC_KEY` in both the API and worker environment; do not commit it. This is separate from the JWT signing secret.
4. Set `OCCUPANCY_SYNC_ENABLED=true` consistently for API and worker. Defaults are disabled. Demo mode disables configuration mutations and execution.
5. Run Redis, a Celery worker and Celery beat using the existing deployment profile. Beat schedules `refresh_occupancy_calendars` every minute; each invocation processes at most 10 due connections sequentially. Scale workers for larger queues and monitor the existing background-service health checks. Scheduled times are not execution guarantees.
6. Test a real supported provider in private staging: connect, observe success, change/cancel dates, verify conflict preservation, pause, resume and disconnect. Automated tests use mocked provider downloads; a real provider account has not been verified by this change.

Saved URLs use [Fernet authenticated encryption](https://cryptography.io/en/latest/fernet/) and are never returned by the API or passed as Celery task arguments/results. Only the worker decrypts a URL for retrieval. Back up the encryption key separately from the database. Losing/changing it makes existing URLs unreadable: pause connections, deploy the new key consistently, then have owners reconnect their links. No automatic key rotation is provided. Do not log request bodies, task locals or plaintext URLs in tracing systems.

The existing URL restrictions apply on every fetch: exact HTTPS allowlist, public DNS validation, pinned address, TLS hostname checks, no redirects or forwarded app credentials, bounded response size and time. Provider URLs must never point back to Bookica exports of the same inventory; circular feeds can retain stale occupancy.

## Scheduling and recovery

Workers claim connection rows with PostgreSQL `FOR UPDATE SKIP LOCKED` and a two-minute lease. No database transaction is held during network access. A worker crash leaves a lease that can be reclaimed after expiry. Results are applied under the listing/venue booking lock only while the lease token, owner, source revision and connection are still current. Expired/replaced jobs are discarded. Pause, reconnect, disconnect and source removal invalidate in-flight results. Owner/property changes disable the connection; reconnect under the current owner to proceed.

A manual source import during a fetch causes the older fetched result to be discarded and another attempt scheduled one minute later. Download/format/key failures preserve blocks and retry after 15 minutes. Conflicts and empty-snapshot guards preserve blocks and retry hourly. Successful source updates and their status/history commit together; rolled-back writes do not claim success. The task has 240-second soft and 270-second hard limits. Provider DNS resolution can outlive a request timeout as documented for one-shot fetching.

The server-wide switch is environment-based, so change it on all API/worker instances. For an immediate per-source stop without waiting for deployment, use pause/disconnect; completed prior updates are not undone.

## Status and API

`GET /owner/properties/{property_id}/occupancy-sources/{source_id}/sync` returns configured/enabled/available flags, running state, next planned run, latest automatic attempt/success and a sanitized outcome. It never returns plaintext or encrypted URLs. `overdue` indicates an enabled connection more than 15 minutes beyond its planned run without a live lease. A recent success does not guarantee a provider has not changed since then.

`POST` to the same endpoint accepts `action`: `connect`, `pause`, `resume`, `refresh` or `disconnect`. Connect also requires `url` and optionally `allow_empty` (default false). Owner/admin access and production per-account/IP budgets apply. Responses use private/no-store caching. Connection changes invalidate manual previews through the source revision.

Outcomes: `pending`, `applied`, `conflict`, `fetch_error`, `key_error`, `blocked_empty`, `superseded`, `inactive`, or `unconfigured`. The UI polls while the automation panel is open, every 30 seconds, and supports explicit retry/status refresh. Refresh the availability list after a completed job to see updated blocks. Valid automatic imports also appear in the shared import history; fetch failures and empty-feed guards are represented in automatic status instead.

This is eventual, date-only synchronization, not a channel-manager guarantee. Provider publication delays, hourly polling, outages and conflicts can leave stale occupancy. Staging acceptance and operational monitoring remain required before public use.
