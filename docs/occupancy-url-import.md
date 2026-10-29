# Import an occupancy calendar from a URL

In the owner's short-stay availability panel, enter a private iCal HTTPS link and choose **Preuzmi i pregledaj link**. Bookica downloads a snapshot, strips descriptive metadata and shows the existing import preview. **Potvrdi uvoz blokada** imports exactly that reviewed snapshot, with the usual fresh availability check under the apartment lock. Confirmation does not fetch the URL again. Successful and conflicting confirmation attempts appear in manual import history.

This is a one-shot import, not a stored calendar connection. URL changes and cancellations are not automatically applied. Repeated imports remain additive; remove outdated blocks explicitly. Recurrence, timed events and additional components remain unsupported; all [file import constraints](occupancy-calendar-import.md) apply.

## Configuration

Set `OCCUPANCY_IMPORT_ALLOWED_HOSTS` to a comma-separated list of exact provider hostnames, for example `calendar.provider.example,feeds.provider.example`. Use the actual host from the provider's HTTPS export URL. Subdomains are not implicitly trusted; wildcards are not supported. Empty (the default) disables URL fetching while file import continues to work. This setting is read from the application's environment, including the production Compose env file. No schema migration or new dependency is needed.

Only approve providers you trust to serve occupancy calendars. The fetcher accepts HTTPS on port 443, rejects URL credentials/fragments/control characters and literal IPs, verifies that all DNS answers are public, then connects to one of those exact addresses. TLS verification and SNI still use the original hostname. It does not follow redirects, honor environment proxy settings, or forward Bookica authentication cookies/headers. Operators should additionally restrict outbound network access to match their deployment requirements.

Responses must be HTTP 200, uncompressed UTF-8 and no larger than 100,000 bytes. The TLS/network socket has a 5-second inactivity timeout and a 15-second connection/read shutdown timer; the request awaits the worker for at most 20 seconds. DNS resolution uses the OS resolver and a timed-out worker may finish cleanup later. Provider compatibility should be verified in private staging; no real provider account was used in automated tests.

Production uses the shared Redis property-write limiter: 6 downloads per account and 30 per IP per minute, across listing IDs. Development can enable it with `PROPERTY_RATE_LIMIT_ENABLED=true`. Demo mode rejects URL downloads. Empty configuration returns 503; unsupported URLs/formats return 400; failed provider responses/downloads return 502; exceeded budgets return 429 with Retry-After.

## Data handling and API

`POST /owner/properties/{id}/occupancy-import/url` accepts `{ "url": "https://…" }` and returns `{ "content": "BEGIN:VCALENDAR…" }` with private/no-store cache headers. The response contains only validated date/status fields; source event names, guest descriptions and URLs are removed. The existing preview/confirmation endpoints process that sanitized content.

Treat provider URLs as passwords. They are sent in the request body, never persisted in Bookica, and cleared from the UI after successful preview. Provider failure messages are generic and do not echo the URL. Do not enable request-body logging in proxies or tracing tools for this endpoint. The provider receives the calendar path/query and the server's IP, as with any download.
