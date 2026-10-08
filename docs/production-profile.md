# Production deployment profile

`compose.production.yml` is a standalone single-host profile. Do not combine it with the development `docker-compose.yml`: that would reintroduce development ports, mounts and commands. It builds immutable application images and serves compiled frontend assets through an unprivileged Nginx container. PostgreSQL and Redis have persistent volumes and no published ports. Backend, worker and scheduler run as UID 10001 without source bind mounts; frontend runs as UID 101. Application roots are read-only, with temporary directories and a dedicated Beat state volume where needed.

This prepares deployment infrastructure; it does not provision a host, domain, certificate, storage account, backup system or access-controlled public demo. Remaining P0/P1 requirements still apply. In particular, keep an internet-facing demo behind a trusted access-control/TLS proxy until the launch gates are satisfied.

## Configure and start

Requirements: a Linux Docker host, recent Docker Compose v2 supporting `--wait`, and enough memory for the configured limits (about 3 GB total container limits plus OS/build overhead). Limits are initial budgets, not measured capacity guarantees.

1. Copy `.env.production.example` to `.env.production` and restrict file access to the operator. Fill the PostgreSQL password, database URL and a strong random JWT secret. Do not commit the file. The URL must point to `postgres:5432` and match the database name/user/password; URL-encode credentials in the URL. Compose rejects missing/empty required credentials. Production startup also validates these values; see the secret-validation section below.
2. Set the real frontend URL/origins. Configure external private photo storage and any approved email relay. This profile does not start MinIO or MailHog. The current SMTP client still lacks authentication/TLS, so account email needs a trusted relay or the planned email integration. Leave Google credentials blank unless its real callback has been configured. Keep live payments disabled for a demo.
3. Build and start from the repository root:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml up --build --wait --wait-timeout 180
```

The default published listener is **127.0.0.1:8080**, not a public interface. Set `BOOKICA_HTTP_PORT` if this port is occupied. If using another configuration path, set both `BOOKICA_ENV_FILE` and `--env-file` to that path: Compose interpolation and container environment loading are separate operations. `config --quiet` avoids printing resolved secrets.

PostgreSQL/Redis health checks gate startup. The one-shot `migrate` service runs `alembic upgrade head` before the API. Frontend, worker and Beat wait for database readiness through the API. Run only one Beat scheduler for this deployment. Failed migrations prevent dependent services from starting.

## Proxy contract

A host-level TLS/access-control proxy should forward the chosen domain to `http://127.0.0.1:8080`, preserve the original Host and overwrite forwarded headers with trusted values. Do not expose this HTTP listener publicly or accept arbitrary client-supplied forwarding headers at the outer proxy. The API trusts forwarding headers because it has no published port and is reachable only on the deployment's trusted container networks.

- `/api/...` is forwarded to FastAPI with the prefix removed; Uvicorn uses `root_path=/api` for generated URLs.
- Google state cookies are rewritten from `/auth/google` to `/api/auth/google`; set the external callback accordingly and use secure cookies under HTTPS.
- `/properties/123`, `/owner` and other client routes fall back to `index.html`. Missing `/assets/...` files return 404 instead of HTML.
- Hashed assets are cached for a year; HTML is revalidated. Private API responses are not proxy-cached.
- Docker DNS is re-resolved so an API container replacement does not permanently strand the proxy on its old IP.
- Upload requests are capped at 12 MB by Nginx; application photo limits still apply. There is no automatic rate limiter in this profile.

Health checks: `/healthz` checks the frontend process; `/api/ready` checks API/database reachability. Container restart policy handles process exits, but an unhealthy status alone does not trigger a restart. Worker/Beat health probes are described below; queue backlog, external-storage/email monitoring and operator alerts remain operational requirements.

## Releases and data

Set `BOOKICA_IMAGE_TAG` to a release identifier when building. For the next version, back up and review migration compatibility first, build images, then use a maintenance window:

```bash
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml stop frontend backend worker beat
docker compose --env-file .env.production -f compose.production.yml run --rm --no-deps migrate
docker compose --env-file .env.production -f compose.production.yml up -d --force-recreate --wait --wait-timeout 180
```

Ensure PostgreSQL is running before the migration command. If migration fails, stop the release and investigate; do not start incompatible application images. The final startup rechecks migrations (already at head). Do not run concurrent releases. `restart` alone does not deploy new code or rerun migrations.

Named volumes retain PostgreSQL data, Redis append-only data and Beat's schedule across ordinary restarts/recreation. **Do not use `down --volumes` on a deployment you want to retain.** Volumes are not backups. Restoring old images may be incompatible with a new schema; a tested recovery/rollback plan remains required. Changing a PostgreSQL password in the env file does not rotate an already initialized database password.

SQL echo is off by default (`SQL_ECHO=false`) to avoid logging statement parameters. Container logs rotate at 10 MB with three files each. Logs still require access controls and review for personal data. The new production Dockerfiles use explicit source copies and non-root users; `.dockerignore` excludes environment files, local tooling and key files. Production startup rejects known placeholder secrets. Canary checks validate build isolation; a full repository/history secret audit and comprehensive image hardening are not claimed complete.

## Validation and limits

The `Production profile` GitHub workflow builds both images and starts isolated PostgreSQL, Redis, migrations, API, worker, Beat and frontend. It checks SPA/static routing, cache headers, real registration/login, privileged-signup rejection, OAuth cookie paths, runtime UID and image exclusions, then recreates the API and repeats checks against the same database. Its generated credentials and sample account are disposable; cleanup deletes only that job's isolated volumes.

`python deploy/smoke_test.py` is for that isolated test environment only: it creates a fixed smoke account. It is not a production monitoring probe and must not be run against customer data. CI does not validate real DNS/TLS, Google credentials, email delivery, photo storage persistence, backup restore or capacity. The broader hosted acceptance test remains on the roadmap.

References: [Compose startup ordering](https://docs.docker.com/compose/how-tos/startup-order/), [FastAPI behind a proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).

## Production secret validation

The production API image defaults to `APP_ENV=production`; Compose explicitly enforces it for API, migrations, worker and Beat. All load the same validated settings before opening application connections. Development/test settings retain local compatibility. Do not override the image environment to bypass these checks.

Generate independent random values (for example with Python `secrets.token_hex(32)`) for JWT and database credentials. JWT requires at least 32 characters, database passwords at least 16; repeated single-character strings and known placeholder markers are rejected. This detects common configuration mistakes, not mathematical entropy. The decoded PostgreSQL URL password must match `POSTGRES_PASSWORD`; URL-encode special characters. Keep `SQL_ECHO=false`.

Google and explicit S3 key credentials must be supplied as complete pairs or left disabled. Configured Google/S3/Stripe secret values must pass placeholder checks; live Stripe keys still require explicit opt-in. S3 workload identity can leave both key fields empty. Validation does not verify remote credentials or grant access to a provider. Error messages name the invalid setting without printing its value; Pydantic validation tracebacks suppress input values. Never log settings dictionaries or structured validation errors, which may still contain inputs.

CI injects disposable canaries into excluded environment, tooling, cloud/SSH credential and key paths. It builds an image of the actual filtered build context and scans saved context/API/frontend/builder image archives, including layers and metadata, for those canaries and generated runtime credentials. The frontend builder scan also covers the compiled bundle. A separate container command proves that a placeholder JWT prevents production settings import without exposing it in the diagnostic. This verifies the tested exclusion paths and known values; it cannot prove that arbitrary secrets have never been committed or detect every encoded/transformed secret. Keep credentials out of source and all `VITE_*` variables (which are public build inputs).

The canary preparation helper is only for a fresh disposable CI checkout and refuses to overwrite its fixture files. Do not run it in an operator checkout containing real credentials. Supply `.env.production` at runtime, restrict access, and rotate credentials through the actual provider/database when necessary; editing the environment file alone does not rotate existing credentials.

## Domain and login configuration

Production uses a single public origin: the built frontend calls `/api`, and the trusted outer TLS proxy forwards to the loopback Nginx listener. Set `FRONTEND_URL` to the exact HTTPS origin without a trailing slash, path, user information, query or fragment (for example the eventual `https://bookica.your-domain.tld`). The committed `.example` template is intentionally rejected until replaced. Use a DNS hostname; configure any non-default HTTPS port consistently. `FRONTEND_ORIGINS` is a comma-separated list of explicit HTTPS origins and must contain that same value. Wildcards, HTTP origins and empty list entries are rejected. These checks validate configuration, not DNS ownership, certificate validity or reachability.

For Google login, configure both Google credentials, set `OAUTH_COOKIE_SECURE=true`, and register exactly `FRONTEND_URL` plus `/api/auth/google/callback` with Google. The production validator rejects a different host, missing `/api` prefix or additional query parameters. Keep both credentials empty to disable Google; its unused callback is then ignored. The public `GET /api/auth/providers` response contains only a Boolean availability flag and uses `Cache-Control: no-store`; it never returns credentials. The login dialog fetches it when opened, hides Google while loading or on failure, and keeps email login usable. LinkedIn, X and Facebook buttons have been removed because no supported backend login flow exists for them. Configuration presence does not prove that Google accepts the credentials.

Before checking off the domain/HTTPS roadmap item, use access-controlled staging to record:

1. The selected domain resolves to the intended host and HTTPS presents a valid certificate; HTTP redirects to HTTPS at the outer proxy.
2. `/api/ready` returns database readiness through that proxy; direct reloads of `/properties/<published-id>` and `/owner` work, and assets have the intended cache headers.
3. The provider endpoint and login dialog agree with the actual configuration. If Google is enabled, complete a real round trip and inspect the secure, HttpOnly, SameSite=Lax state cookie under `/api/auth/google`.
4. Frontend origin, callback and forwarded headers agree with the chosen domain. The loopback application listener remains inaccessible directly from the internet.

The container smoke test uses the non-resolving `https://bookica.test` configuration solely to exercise production validation and the proxied OAuth redirect/cookie; requests still use the isolated HTTP loopback listener. It does not obtain a TLS certificate or contact Google. Public hosting remains deferred until P0, P1 and P2 are complete, per the launch decision.

## Background service checks and persistence

Production Compose has health checks for worker and Beat. Inside each worker, `python -m app.runtime_health worker` sends a Celery inspect ping to that container's default `celery@hostname` node only. Another worker replying cannot hide its failure. If you change Celery node naming, update the probe as well. This checks the worker control process, not successful business-task execution.

Beat schedules `record_scheduler_heartbeat` every 30 seconds on the regular queue. A worker executes it and writes an expiring marker in the Redis broker database, with no customer data and no result record. `python -m app.runtime_health scheduler` checks its value and positive TTL (at most 90 seconds). This demonstrates recent scheduling, broker delivery and worker execution together; it is not a PID check and does not isolate which component failed. Startup has a 90-second grace period. Messages expire after 60 seconds to bound delayed heartbeat execution, and stale markers expire automatically. A recent marker may temporarily survive a restart; repeated checks, not one initial green result, establish ongoing health. Queue saturation can make this probe fail, which should prompt investigation.

Keep exactly one Beat per deployment and isolate broker databases across environments. Multiple schedulers sharing this key could mask each other's failure and duplicate business work. The probe intentionally does not delete markers, enqueue business tasks or print exception details/connection strings. Docker marks a container unhealthy after repeated failures; it does not automatically restart an unhealthy live process. Configure operator alerting and recovery under the P1 operations milestone.

Read-only operator checks:

```bash
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml exec -T worker python -m app.runtime_health worker
docker compose --env-file .env.production -f compose.production.yml exec -T beat python -m app.runtime_health scheduler
```

The isolated CI stack stops Beat and waits for heartbeat expiry, then recreates PostgreSQL/Redis and application containers with the same volumes. It requires the original account to already exist (409 on repeat registration plus successful login), checks a temporary Redis marker, and requires worker/scheduler recovery. These are graceful recreation tests, not crash/power-loss guarantees or backup/restore drills. The CI operations stop services and must not be copied into an active customer deployment as health probes.

Private photo storage has not been provisioned. This change does not verify a real photo bucket, email delivery or the result of a scheduled saved-search notification; those require staging acceptance before the P0 service milestone can be checked off.

References: [Celery inspect destinations](https://docs.celeryq.dev/en/stable/userguide/monitoring.html#specifying-destination-nodes), [periodic tasks and single scheduler](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html).
