# Bookica

Bookica is a full-stack booking and reservation platform for discovering venues, checking live availability, receiving an exact quote, and reserving spaces. It also provides owners and staff with tools for managing venues, availability, customers, payments, promotions, analytics, and day-to-day operations.

## Contents

- [What is included](#what-is-included)
- [Technology](#technology)
- [Backend guide](#backend-guide)
- [Using Bookica](#using-bookica)
- [Quick start with Docker](#quick-start-with-docker)
- [Local development](#local-development)
- [Google login](#google-login)
- [Validation](#validation)
- [Project structure](#project-structure)
- [API overview](#api-overview)

## What is included

### Customer experience

- Responsive React storefront for desktop, tablet, and mobile
- Venue search, category shortcuts, popular venues, ratings, and availability
- Venue and resource details with capacity, price, and cancellation information
- Server-calculated quotes, promotion codes, and expiring reservation holds
- Email/password authentication, Google OAuth, and password recovery
- Secure check-in passes, reservation guests, transfers, waitlists, and waivers
- Favorites, reviews, notifications, support tickets, and calendar feeds
- First-visit page guide that remains dismissed with a browser cookie
- Accessible dropdown navigation, mobile menus, dialogs, drawers, and venue cards

### Owner and operations API

- Venue, resource, staff, availability-rule, and availability-exception management
- Capacity-aware bookings, recurring reservations, rescheduling, and cancellation policies
- Payments, refunds, add-ons, promotion codes, and customer access controls
- Maintenance work orders, reservation reminders, no-show handling, and audit history
- Venue analytics, demand insights, and CSV exports
- Review moderation, API keys, webhooks, and webhook-delivery retries
- Background processing with Celery and Redis
- Development email delivery through MailHog

## Technology

- Backend: Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, Alembic
- Frontend: React, TypeScript, Vite
- Background jobs: Celery and Redis
- Development services: Docker Compose and MailHog
- Testing and quality: pytest, Ruff, ESLint, TypeScript, and Vite production builds

## Backend guide

The FastAPI backend uses a layered structure:

```text
HTTP request
    -> API router and dependency checks
    -> service containing business rules
    -> repository/database operations
    -> SQLAlchemy model in PostgreSQL
```

Pydantic schemas define API input and output contracts. Alembic owns schema changes, while Celery workers handle scheduled and retryable work through Redis.

### Authentication and authorization

- Passwords are hashed before storage and successful login returns a JWT bearer token.
- Google OAuth can create or connect an account using the provider's stable identity.
- Protected endpoints accept either `Authorization: Bearer <token>` or `X-API-Key: <key>` where API-key access is supported.
- Application roles are `customer`, `owner`, and `admin`.
- Venue staff can separately be assigned as `manager` or `check_in_agent` for a specific venue.
- JWT token versions allow previously issued tokens to be invalidated.

### Reservation lifecycle

Reservations move through `pending`, `confirmed`, `cancelled`, `completed`, and `expired` states. Attendance is tracked separately as `scheduled`, `checked_in`, or `no_show`.

The reservation service provides:

- Availability and capacity validation before creation
- Server-owned pricing and promotion calculations
- Idempotency keys to prevent duplicate creation requests
- Temporary holds with configurable expiration
- Payment confirmation and full or partial cancellation refunds
- Rescheduling, recurring series, transfers, guests, add-ons, and waitlists
- Signed check-in passes, attendance tracking, reminders, and audit events

Payment records move through `pending`, `paid`, `failed`, `partially_refunded`, and `refunded`. The current service uses a mock payment provider so the workflow can be developed and tested without transmitting real payment details.

### Background jobs

Celery Beat schedules work and Celery workers execute it. The included periodic tasks:

- Expire unpaid reservation holds
- Mark eligible reservations as no-shows
- Send upcoming reservation reminders
- Deliver or retry due webhook notifications

Intervals and broker/result URLs are configured through the backend environment variables documented in `.env.example`.

### Main API groups

| Area | Base path | Purpose |
| --- | --- | --- |
| Authentication | `/auth` | Registration, login, Google OAuth, password recovery, user identity, and API keys |
| Venues and resources | `/venues`, `/resources` | Catalog management, search, availability, staff, policies, and reservable resources |
| Reservations | `/reservations` | Quotes, booking, pagination, details, changes, cancellation, check-in, and history |
| Payments and offers | `/payments`, `/promotions` | Payment status, refunds, and venue promotion codes |
| Owner operations | `/owner`, `/analytics` | Dashboards, performance summaries, demand insights, and CSV exports |
| Customer tools | `/favorites`, `/notifications`, `/support` | Saved resources, notifications, and support conversations |
| Trust and safety | `/resources`, `/review-moderation`, `/waivers` | Reviews, reports, moderation, and waiver signatures |
| Venue operations | `/venues/{venue_id}` | Staff, customer blocks, maintenance, calendar feeds, add-ons, and webhooks |
| Waitlist | `/waitlist` | Joining, viewing, and leaving resource waitlists |
| Administration | `/admin` | Platform-wide operational summaries |

Some related resources use nested paths. The generated OpenAPI page at `/docs` is the authoritative endpoint reference.

## Using Bookica

### Navigating the storefront

- **Explore** opens shortcuts for all spaces, workspaces, sports, events, and wellness venues.
- **How it works** explains the discover, choose, and reserve flow.
- **List your space** takes prospective owners to the owner section.
- On phones, the same destinations are available from the menu button in the header.
- Signed-in users can open their avatar menu to explore spaces, revisit the booking guide, reach the owner section, or log out.
- A short navigation bubble appears on the first visit. Closing it stores a long-lived cookie so it does not appear again in that browser.

### Signing in with Google

Google OAuth must first be configured as described in [Google login](#google-login). Once configured:

1. Select **Log in** on the storefront.
2. Choose **Google** in the login dialog.
3. Sign in and approve the request on Google's page.
4. Google returns to the backend callback, which verifies the OAuth response and redirects to Bookica.
5. Bookica stores the issued access token in the browser and loads the signed-in profile.

If Google reports a redirect error, confirm that the URI in Google Cloud exactly matches `GOOGLE_REDIRECT_URI`. The frontend displays a configuration message when the provider is not configured.

### Finding and reserving a space

1. Enter a venue name, address, description keyword, or category in the hero search field, then select **Find a space**.
2. Alternatively, use the Explore menu, category cards, popular venues, or limited-time offers.
3. Select a venue to open its details and available resources.
4. Choose a resource, date, start time, duration, guest count, and optional promotion code.
5. Review the server-calculated quote and select **Reserve this space**.
6. Sign in when prompted. A successful reservation receives a temporary hold that must be paid before it expires.

The public backend also supports paginated venue and resource search at `/venues/search`, `/resources/search`, and `/resources/search/available`. The available-resource search accepts a time range, minimum capacity, resource type, and optional text query.

### Adding venues and resources as an owner

The owner catalog workflow is currently available through the API; a complete owner upload dashboard has not yet been added to the storefront. There is also no venue-image upload endpoint yet—“adding” currently means creating venue and resource records.

To add inventory through the interactive API:

1. Open <http://localhost:8000/docs>.
2. Sign in with an account whose application role is `owner` or `admin` and copy its bearer token.
3. Select **Authorize** in the OpenAPI page and enter the token.
4. Call `POST /venues` with the venue name, address, description, booking rules, and cancellation policy.
5. Copy the returned venue ID and call `POST /venues/{venue_id}/resources` for each bookable room, court, desk, or other resource.
6. Configure availability rules or exceptions under `/resources/{resource_id}/availability-rules` and `/resources/{resource_id}/availability-exceptions`.
7. Optionally configure add-ons, promotions, staff, maintenance, calendar feeds, customer blocks, and webhooks using the matching venue endpoints.
8. Refresh the storefront; public venues and their resources are loaded from the API.

Creating or promoting owner/admin accounts should be controlled by an administrator in a deployed environment. Never place an owner token or API key in frontend source code.

## Quick start with Docker

Requirements: Docker and Docker Compose.

1. Review `.env.docker` and replace development secrets before using the stack outside a local environment.
2. Start the services:

   ```bash
   docker compose up --build
   ```

3. Apply the database migrations in another terminal:

   ```bash
   docker compose exec backend alembic upgrade head
   ```

The services are then available at:

- Bookica frontend: <http://localhost:5173>
- FastAPI documentation: <http://localhost:8000/docs>
- API health check: <http://localhost:8000/health>
- MailHog inbox: <http://localhost:8025>

## Local development

Requirements: Python 3.12, Node.js, PostgreSQL, and Redis.

### Backend

Create a virtual environment, install the dependencies, and copy the environment template:

```bash
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Then configure and start the API:

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Do not commit `.env`; it contains local secrets and credentials.

### Frontend

From the `frontend` directory:

```bash
npm install
npm run dev
```

During local development, Vite proxies `/api` requests to `http://localhost:8000`. Copy `frontend/.env.example` to `frontend/.env` only when you need to override the API or proxy target.

## Google login

Google login requires an OAuth client ID and secret. Add the following values to the backend environment:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_URL=http://localhost:5173
OAUTH_COOKIE_SECURE=false
```

The authorized redirect URI in Google Cloud must exactly match `GOOGLE_REDIRECT_URI`. See [GOOGLE_LOGIN_SETUP.md](GOOGLE_LOGIN_SETUP.md) for the complete setup procedure.

## Validation

Run the backend test suite and formatting checks from the repository root:

```bash
pytest
ruff check .
ruff format --check .
```

Run the frontend checks from `frontend`:

```bash
npm run lint
npm run build
```

## Project structure

```text
app/
  api/routers/       HTTP endpoints grouped by feature
  core/              Configuration, authentication dependencies, caching, and security
  db/                Async SQLAlchemy engine, sessions, and model registration
  models/            Persistent database entities and state enums
  repositories/      Focused database queries and persistence operations
  schemas/           Pydantic request and response contracts
  services/          Business rules and transaction workflows
  tasks/             Celery configuration and background jobs
  main.py            FastAPI application and router registration
alembic/             Migration environment and versioned database changes
frontend/src/
  App.tsx            Storefront UI and customer interactions
  api.ts             Typed frontend API client and authentication storage
  types.ts           Shared frontend response types
  styles.css         Desktop and responsive presentation
tests/               Backend unit and integration-style service tests
docker-compose.yml   Local application and infrastructure stack
```

When adding a backend feature, the usual path is model and migration, schema, repository or service logic, router, and tests. Keep business rules in services rather than routers. When adding a frontend feature, update the API client/types first, then the UI and responsive styles, and finish with lint and production-build validation.

## API overview

The API includes endpoints for authentication, venues, resources, reservations, payments, promotions, availability, owners, analytics, favorites, notifications, reviews, support, maintenance, staff, waitlists, webhooks, waivers, and administrative operations.

Use the interactive OpenAPI documentation at `/docs` for current request bodies, response schemas, and authorization requirements.
