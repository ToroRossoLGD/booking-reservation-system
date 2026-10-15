# Unknown-page recovery

Unknown application URLs now show a Serbian not-found page with a single main
landmark, keyboard skip-link support and explicit links to the property catalog
and account. They no longer silently load the legacy booking app or an unrelated
owner/account dashboard. The browser title and sharing descriptions identify the
not-found state without copying arbitrary paths, query parameters or fragments.

Supported routes are listed in `frontend/src/routing.ts`; add new page routes
there alongside their RootPage renderer. One trailing slash is accepted without
redirecting or rewriting the address. Repeated slashes are not collapsed, and
encoded path components are not decoded into different routes. Password-reset
and verification token extraction uses the same normalization and still removes
credential fragments before rendering. Public property pages retain their own
invalid-ID/unavailable feedback.

This is a client-side UX improvement. The static SPA host still serves its HTML
fallback with HTTP 200 for application paths; this change does not implement
server-side HTTP 404 responses or crawler indexing rules. API/asset status codes
and nginx routing are unchanged. No migration or new configuration is required.

Tests cover supported routes, unknown account/owner paths, trailing-slash links,
metadata cleanup, return links and browser history, keyboard/mobile access and
recovery/verification links with credential fragments. Broader P1 hosted and
accessibility acceptance remains open.
