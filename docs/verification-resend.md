# Email verification resend

After a successful resend request, `/verify-email` disables the resend button for
60 seconds, matching the existing service cooldown. The countdown uses a deadline
rather than counting timer callbacks, so background-tab delays do not extend it.
The button becomes available without a page reload; sending always requires a click.

On HTTP 429 the resend flow honors parsed `Retry-After` seconds, with a 60-second
UI fallback if the header is missing. Server limits remain authoritative, including
after navigation/reload: this local countdown is usability feedback, not an abuse
control. Confirmation links keep their existing behavior.

The countdown is ordinary text to avoid per-second live announcements. A status
message announces when retry is available. The interval stops on expiry or unmount.
Generic delivery wording does not promise delivery or reveal account existence.

Desktop/mobile browser coverage advances the browser clock through the cooldown
and verifies deliberate repeat submission. Another scenario checks a longer server
wait and verifies that expiry alone sends nothing. Existing verification unit tests
cover token and authentication behavior. No API, migration or configuration changes.
Private HTTPS staging/email-provider acceptance remains open in P1.
