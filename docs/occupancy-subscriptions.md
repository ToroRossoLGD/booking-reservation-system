# Live occupancy calendar subscriptions

Owners and administrators can open a short-stay listing's availability panel and choose **Podesi iCal pretplatu** to create, replace or revoke a subscription link. Creation and revocation require confirmation. Copy the generated URL into an external calendar's subscription/import-by-URL field. The secret is shown only after creation or replacement; it cannot be retrieved later.

Each request returns current occupancy for the next 365 local days, using the same privacy-preserving export as the [manual snapshot](occupancy-calendar-export.md): confirmed stays, preparation gaps and active blocks, merged across listings sharing an apartment. Events contain unavailable dates, not guest details or private block reasons.

## Lifecycle and API

- `GET /owner/properties/{id}/occupancy-feed` returns status only.
- `POST /owner/properties/{id}/occupancy-feed` creates or replaces the link and returns its path once.
- `DELETE /owner/properties/{id}/occupancy-feed` revokes it; repeated revocation is safe.
- `GET /occupancy-feeds/{token}.ics` reads the calendar without account authentication. In the default deployment these routes have an `/api` prefix.

There is one active link per apartment, shared by its listing aliases. Management requires the owner or an administrator. Mutations are disabled in demo mode. Rotation and revocation serialize on the apartment lock. Tokens have 256 bits of randomness; only a SHA-256 digest is stored. Old links return 404 after replacement/revocation. A change of apartment owner invalidates access while ownership differs from the recorded issuer. A failed creation response can be recovered by generating a replacement, which invalidates the previous token.

Anyone holding the URL can read occupancy. Use HTTPS and treat the URL as a password. Revocation prevents future reads, but cannot retract completed downloads or requests already in progress. The frontend keeps the returned secret only in component memory.

## Deployment

Run `alembic upgrade head` before deploying (migration `b83f04e9c712`). The bundled Nginx configuration suppresses access and error logging for the public feed route; the application filters its Uvicorn access entries. Any additional reverse proxy, CDN, tracing or analytics system must also exclude or redact these secret-bearing URLs. Do not paste real subscription URLs into tickets or logs.

## Scope

This is outbound calendar subscription support. External clients decide their refresh interval, so changes may not appear immediately and this does not prevent double bookings across platforms. External calendar import, scheduled inbound refresh, conflict handling and last-sync reporting remain on the roadmap. Use the existing manual download for a one-time snapshot.
