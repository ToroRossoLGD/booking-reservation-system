# Analytics data pipeline

The application keeps transactional booking data normalized for safe writes. Reporting
has different access patterns, so a nightly ETL job materializes one row per venue/day
and one row per resource/day in `daily_venue_metrics` and `daily_resource_metrics`.

## Flow

1. Celery Beat starts `refresh_daily_analytics_task` at
   `CELERY_ANALYTICS_REFRESH_HOUR_UTC` (02:00 UTC by default).
2. The task extracts yesterday's reservations, their resources, and optional payments.
3. It transforms them into reservation, customer, booked-time, capacity-time,
   cancellation, no-show, status, and currency-safe revenue metrics.
4. Data-quality checks reconcile every additive venue metric and revenue amount to its
   resource-level children.
5. In one database transaction, the loader deletes and recreates the requested dates.
   It also records the refresh metadata in `analytics_pipeline_runs`. This makes retries
   and historical backfills idempotent while preserving an operational audit trail.

Only payment states recognized by the existing analytics service contribute revenue.
Currency values remain separate; amounts with different currencies are never added.

## Operations

Apply the migration with `alembic upgrade head`. An administrator can backfill up to
366 days with:

```http
POST /analytics/pipeline/refresh?start_date=2026-01-01&end_date=2026-08-27
```

Owners and administrators can query persisted venue metrics with:

```http
GET /analytics/venues/7/warehouse?start_date=2026-08-01&end_date=2026-08-27
```

Administrators can inspect manual and scheduled refresh history with:

```http
GET /analytics/pipeline/runs?limit=20&offset=0
```

Each run records its covered date range, trigger, completion time, source reservation
count, generated venue/resource rows, and passed reconciliation checks. A run appears
only when the warehouse replacement and audit record commit successfully together.

The operational analytics endpoints remain available. The warehouse endpoint is meant
for dashboards, BI exports, and future forecasting without repeatedly scanning raw
reservation/payment rows.
