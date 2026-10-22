# Listing report form usability

The public listing report form explains its minimum trimmed description length
and 2000-character limit, with a visible count. Submitting an empty/short description
now produces Serbian guidance and focuses the field instead of leaving the submit
button disabled without explanation. Overlong values are also rejected locally.

The description references its hint and validation error with unique IDs and
`aria-describedby`; invalid state is exposed with `aria-invalid`. Editing clears
stale validation errors. The counter is not a live region, avoiding announcements
on every keystroke. Pending submission still disables the fieldset.

**Zatvori obrazac** closes the form without submitting and restores focus to
**Prijavi oglas**. Reopening retains input and any retry request ID while the
component stays mounted; nothing is persisted to browser storage. Leaving or
reloading the page discards the draft. The trigger references its panel through
`aria-controls`; successful submission focuses the confirmation and its history
link. Browser coverage verifies keyboard closing, retained text and success focus.

Privacy guidance, authenticated server validation, rate limits and idempotent retry
are unchanged. Invalid input sends no report; a failed valid request retains the
description and request ID for retry. No migration or configuration is required.

Unit coverage checks whitespace-only input, focus, correction and retry alongside
existing rate-limit/idempotency tests. The moderation browser flow checks empty
submission before completing a valid report. This is a P1 usability slice only.
# Account changes

The report form resets its draft, category, request UUID, errors and confirmation
when the stored browser session changes in another tab or is detected on window
focus. It also resets for a different listing. Closing/reopening within the same
session still preserves the draft. A response from an older session cannot show
confirmation or errors in the replacement form, and no report is sent automatically.

Switching accounts does not cancel a report already accepted by the server for the
previous account. Desktop/mobile tests cover switching during a pending request,
separate request UUIDs and authorization for the new account, and logout cleanup.
