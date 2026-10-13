# Page titles and sharing metadata

Bookica now assigns Serbian browser titles and short descriptions to account,
recovery, verification, saved listings, stays, rental/sales inquiries, owner,
moderation and legacy booking pages. Navigating between routes updates the
description, Open Graph title/description and Twitter title/description without
leaving metadata from the previous page.

Public listing pages use their public title and a short summary of offer type,
city and area. Loading, unavailable and network-error states use neutral metadata.
Account pages use generic descriptions: email addresses, reservation IDs,
verification/reset tokens, query strings and URL fragments are not copied into
the head. This is not an access-control or search-engine indexing mechanism.

The static HTML includes a generic Bookica title/description, Open Graph site
name/type/locale and a summary-card declaration. Visitors with JavaScript get
route-specific values. Crawlers that do not execute JavaScript receive the
generic static metadata; listing-specific social previews are **not guaranteed**.
There is no server-side rendering, prerender service, canonical URL policy or
share-image pipeline in this change. Those need separate deployment work and
hosted acceptance before declaring the P1 metadata goal fully complete.

Tests cover route-to-listing-to-route transitions, metadata cleanup, duplicate
prevention, text-only insertion, recovery-token exclusion, direct browser links
and public listing/unavailable states. The P1 roadmap records this as a completed
subset and leaves broader UX, metadata and performance acceptance open.
