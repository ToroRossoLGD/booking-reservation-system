# Notification inbox language

The account notification view now uses Serbian for its heading, navigation,
read/dismiss controls, counts, pagination, loading and empty states. Links to the
legacy account tabs identify hourly reservations and resource favorites.
Notification timestamps use `sr-Latn-RS` formatting in the browser's timezone.

Load and mutation failures use controlled Serbian guidance instead of raw backend
error text. Failed mutations preserve the notification and permit retry. Existing
read/dismiss APIs, pagination and property action links are unchanged.

Stored notification titles and messages are shown as received; historical English
notifications are not rewritten. Other legacy dashboard tabs still require language
review. This completes an inbox slice of P1, not full application localization.

Dashboard tests cover pagination, errors, read counts and bulk/individual removal.
Desktop guest and mobile owner browser flows verify reading, refreshing and following
stay links. No migration or configuration change is required.
