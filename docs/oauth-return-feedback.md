# Google sign-in return feedback

Google callback failures return to the frontend home URL with an `auth_error`
fragment. Previously the fragment was consumed eagerly but its message was only
rendered by the legacy booking App, leaving the property home page without an
explanation. Feedback now lives in the root shell and works on the home page as
well as other initial routes, independently of deferred route downloads.

Cancelled and expired/invalid-state returns receive specific Serbian guidance.
Other messages use a generic failure explanation; arbitrary fragment text and
provider diagnostics are never rendered. The existing eager fragment removal is
preserved. The notice offers the configured Google button for a fresh flow and
an email-login link to the account page. No provider request is automatically
replayed. If provider discovery fails or Google is disabled, email recovery and
dismissal remain available.

Dismissal lasts for the current page session. Refreshing after the fragment was
removed does not recreate the notice. The notice itself does not revoke sessions
or remove a saved bearer token. It replaces the legacy App's stale error state,
so navigating to booking after dismissal does not reopen the old error dialog.

Chromium tests cover desktop/mobile cancelled returns, expired state, explicit
provider retry, disabled-provider fallback, unknown-message redaction, fragment
removal and session preservation. Existing OAuth route-loading and provider
discovery tests remain green. These are mocked browser checks; real Google
provider acceptance on private HTTPS staging remains open P1 work.

No backend/API change, migration or new configuration is required. The separate
server-rendered OAuth rate-limit/error page is unchanged.
