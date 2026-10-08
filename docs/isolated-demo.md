# Isolated portfolio demo

This is a disposable, access-controlled demo with fictional data. It is not a customer deployment or a substitute for the remaining P0/P1/P2 launch gates. `DEMO_MODE=true` requires a separate PostgreSQL database whose name ends in `_demo` and matches `POSTGRES_DB`. Use a separate Compose project, volumes, broker and credentials; never enable demo mode on an existing customer environment.

The seed creates three published listings (short stay, long-term rental and sale), an owner and a customer. Their addresses/descriptions are fictional. The three bundled room illustrations in `app/demo_assets.py` are original vector artwork created for this project, clearly marked as illustrations, not photographs of real properties; they contain no third-party images or remote references. Photo access still goes through the normal listing visibility/ownership checks. No object-storage bucket is needed for these assets.

## Configuration and startup

Copy `.env.demo.example` to ignored `.env.demo`. Generate independent random database, JWT, owner and guest secrets; for example use Python `secrets.token_hex(24)` (32 bytes for JWT). Set `DATABASE_URL` to `postgresql+asyncpg://bookica_demo:<URL-encoded-password>@postgres:5432/bookica_demo`. Account passwords must contain 16-72 characters and differ. Never reuse customer credentials or pass passwords as CLI arguments. Restrict access to the env file.

Set `BOOKICA_ENV_FILE=.env.demo` in the shell as well as supplying `--env-file`. The following commands use a separate Compose project:

```bash
export BOOKICA_ENV_FILE=.env.demo
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml up --build --wait --wait-timeout 180
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml stop frontend backend worker beat
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml run --rm --no-deps backend python -m app.demo seed
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml run --rm --no-deps backend python -m app.demo seed --apply
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml up -d --wait --wait-timeout 180
```

For PowerShell, use `$env:BOOKICA_ENV_FILE='.env.demo'` instead of `export`. The local listener is `http://127.0.0.1:18080`; `.test` is configuration only, with no DNS or certificate provisioned. Private staging requires the real HTTPS origin and trusted access-control/TLS proxy. Keep the demo off the public internet until the agreed launch gates are complete.

Login through the normal account dialog: `guest@example.com` uses `DEMO_GUEST_PASSWORD`; `owner@example.com` uses `DEMO_OWNER_PASSWORD`. Distribute customer credentials only to the intended reviewers. Keep owner credentials private; no administrator is seeded and no credentials are exposed by the runtime endpoint or banner. Registration and Google OAuth are disabled to avoid collecting real account/contact data.

## Boundaries and limits

- A global banner identifies fictional data and warns against entering personal information. `GET /runtime-config` returns only the demo Boolean with `no-store` caching.
- Stripe checkout/webhook processing, Google OAuth, email sending and outbound webhook delivery are blocked in services, even if credentials are accidentally configured. In-app notifications and conversations still work and their content stays in the demo database. Existing queued webhooks are not sent.
- Media uploads are disabled (zero writable upload quota), including multipart requests rejected before body parsing. External S3 clients are disabled. Only the three allowlisted bundled illustrations are served; ordinary photo authorization still applies. Deleting a demo photo affects its database row and needs reset to restore it.
- Owner listing edits, sample bookings and inquiries are disposable database changes. Existing per-feature limits apply, but there is no global database-row quota or abuse-rate limiter yet. Use restricted access, monitor disk use and reset between review sessions; this is not ready for anonymous public traffic. Browser map/font providers are not an offline feature; outbound business messages/payments are the blocked integrations.

## Preview-first reset

Stop frontend, API, worker and Beat before resetting so requests and queued business work cannot write during reset. Keep PostgreSQL and Redis running. Take any desired demo snapshot first; all application rows will be replaced. Do not use this tool to clean customer data.

```bash
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml stop frontend backend worker beat
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml run --rm --no-deps backend python -m app.demo reset
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml run --rm --no-deps backend python -m app.demo reset --apply --confirm-database bookica_demo
docker compose -p bookica-demo --env-file .env.demo -f compose.production.yml up -d --wait --wait-timeout 180
```

Without `--apply`, commands only report the target and affected row count. Seed requires empty application tables, writes a dedicated `bookica_demo_guard` marker in the same transaction and is a no-op on an already populated marked demo. Reset requires that marker plus the exact confirmed database name. Unexpected public tables cause refusal. It truncates only the registered application tables, without `CASCADE`, and preserves PostgreSQL sequences so old bearer tokens cannot become valid for newly seeded IDs. API keys and account tokens stored in the database are removed with the rows. An advisory lock serializes demo commands; reset and reseed are one transaction and roll back together on failure. The marker is operational metadata, not an Alembic-managed application table.

The tool does not delete external storage, alter schemas, reset Redis or rotate secrets. Keep the broker exclusive to this demo, and clear obsolete demo queues only through a reviewed maintenance procedure if necessary. Before each public-review session use fresh isolated resources or ensure there are no old pending jobs. After reset, sign in again; data IDs change intentionally. Production configuration continues to default to `DEMO_MODE=false`.

## Evidence

The `Isolated demo` workflow starts the real Compose stack, migrates and seeds it, checks both roles, three offer types, locally served illustrations and blocked registration/uploads/OAuth. It repeats seed, performs a confirmed reset with writers stopped, and verifies new user IDs and rejection of the old customer token. Unit tests cover network guards, target validation and runtime metadata; browser tests cover the visible banner. This proves repository-level demo preparation, not a hosted acceptance test.
