# Property gallery keyboard access

Public property galleries now reuse the shared native modal wrapper for focus
containment, Escape dismissal, background inertness, scroll locking and focus
restoration to the cover button. Their full-screen layout is preserved.

- Tab and Shift+Tab cycle through visible enabled controls, including thumbnails
  and the retry action. Disabled previous/next buttons are skipped.
- Left/right arrows cycle through photos; Home/End select the first/last photo.
  Alt/Ctrl/Meta combinations are left to the browser.
- The close button receives initial focus. Escape or the close action returns
  focus to the gallery cover when it still exists.
- Retrying an unavailable photo returns focus to the close control instead of
  leaving it on a removed retry button.
- Focus outlines contrast with the dark gallery background. Existing photo
  alternative text, selected-thumbnail state and live position counter remain.

Chromium coverage includes desktop/mobile focus cycling, arrow wrapping,
Home/End, background focus rejection, reopening, scroll restoration, single-photo
disabled actions and image failure/retry. Existing upload/reorder/delete and
account-dialog tests guard the shared behavior. No storage/API changes are made.

This is another bounded P1 accessibility improvement. Manual screen-reader and
cross-browser acceptance, broader nonmodal review and hosted mobile performance
remain open. No database migration or configuration change is required.
