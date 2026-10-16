# Password reset form accessibility

The reset form offers **Prikaži lozinke**, a native toggle button with
`aria-pressed` and `aria-controls` for both fields. Values start hidden, retain
new-password autocomplete, disable spell checking/capitalization, and become
hidden again when the form submit handler runs, even if validation or the request
fails. Native required/minimum-length validation can prevent submission before
that handler runs. The toggle is disabled while a request is pending.

A mismatch focuses confirmation; the existing 72-byte UTF-8 limit focuses the
new-password field. Invalid fields reference the Serbian error using
`aria-describedby` and `aria-invalid`. Editing clears stale validation feedback.
Request failures preserve the typed values for retry without exposing them.

Unit coverage includes multibyte length validation, error focus, retained hidden
values after server failure, existing token errors and session removal on success.
Desktop/mobile browser coverage exercises the visibility toggle using a keyboard,
mismatch recovery, field associations and successful password reset.

This completes a P1 form-usability slice only. Real email-provider delivery and
private HTTPS staging acceptance remain open. No API contract, credential storage,
database migration or environment setting changes.
