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

Health checks: `/healthz` checks the frontend process; `/api/ready` checks API/database reachability. Container restart policy handles process exits, but an unhealthy status alone does not trigger a restart. Worker/Beat supervision, queue health and external-storage/email monitoring remain operational requirements.

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
