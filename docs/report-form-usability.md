# Listing report form usability

The public listing report form explains its minimum trimmed description length
and 2000-character limit, with a visible count. Submitting an empty/short description
now produces Serbian guidance and focuses the field instead of leaving the submit
button disabled without explanation. Overlong values are also rejected locally.

The description references its hint and validation error with unique IDs and
`aria-describedby`; invalid state is exposed with `aria-invalid`. Editing clears
stale validation errors. The counter is not a live region, avoiding announcements
on every keystroke. Pending submission still disables the fieldset.

Privacy guidance, authenticated server validation, rate limits and idempotent retry
are unchanged. Invalid input sends no report; a failed valid request retains the
description and request ID for retry. No migration or configuration is required.

Unit coverage checks whitespace-only input, focus, correction and retry alongside
existing rate-limit/idempotency tests. The moderation browser flow checks empty
submission before completing a valid report. This is a P1 usability slice only.
