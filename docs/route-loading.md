# Deferred route loading

The public catalog no longer eagerly imports the legacy booking/owner app,
stays, rental/sales conversations, saved listings, account security, verification
or password-recovery screens. React loads those modules when their routes open.
Property detail, moderation and owner preview/analytics retain their existing
deferred loading. Shared code remains reusable across chunks.

A pending route shows a Serbian status message in the main-content landmark.
A failed module download/render shows a recovery screen with a full-page reload
and a home link. Route changes reset this error boundary. Reloading can discard
unsaved form input; it does not automatically resubmit requests. Recovery links
whose fragments were already consumed may need to be reopened from the email.

OAuth fragment consumption remains eager, before any deferred booking module
loads. Password-reset and email-verification token extraction also remains in
the initial route shell. Moving UI code must not leave credential fragments in
the URL while a module downloads.

Local production builds on this change reduced the main entry JavaScript file
from 576.32 kB (167.47 kB gzip) to 285.58 kB (89.38 kB gzip). These are build-reported
entry-file sizes, not total network traffic or a measured mobile speedup. Shared
chunks and CSS are still needed; other route chunks download on demand. The
previous >500 kB chunk warning is no longer emitted.

Browser tests verify that the home route does not request deferred route/Leaflet
modules, direct booking links still work, failed downloads can be reloaded, and
OAuth fragments are consumed while a route module is deliberately delayed.
Recovery, verification and existing storefront scenarios provide regressions.
The request assertions use Vite's development module names; production build
output provides the separate bundle-size evidence.

This completes the route-splitting portion of P1 UX performance work. Hosted
mobile measurements with real images/maps, cache/deploy acceptance and the
broader P1 launch requirements remain open. No migration or new setting is needed.
