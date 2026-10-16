# Account security recovery and keyboard focus

On `/account/security`, failed account loading now offers **Pokušaj ponovo**
without requiring a full-page refresh. Retrying does not revoke sessions or clear
credentials. A 401 instead offers login and never exposes revocation controls.

Opening the existing inline confirmation focuses **Odustani**, so pressing Enter
does not accidentally confirm a destructive account action. Cancelling returns
focus to **Odjavi sve uređaje**. Successful revocation or an expired session during
revocation focuses the page heading when those controls disappear. A completed
load retry also focuses that heading; initial loading does not steal focus.

Existing semantics are preserved: success clears local credentials, failed
revocation permits retry, and a 401 never claims all sessions were revoked.

Tests cover desktop/mobile account-load recovery, keyboard cancellation, successful
revocation and focus, plus unit coverage for failed/retried/expired requests and
disabled pending controls. No backend migration or configuration changes. This
completes a P1 usability slice; hosted session-security acceptance remains open.
