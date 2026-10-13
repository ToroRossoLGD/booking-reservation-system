# Keyboard-accessible dialogs

The account login/signup, legacy booking, cancellation confirmation and shared
management forms now use a common native modal dialog. This is a completed slice
of P1 core-user-experience work, not a full accessibility audit.

- Each dialog has an accessible name and opens in the browser's modal layer.
- Background controls are inert while it is open; page scrolling is locked.
- Tab and Shift+Tab wrap across enabled, visible controls, including after form
  mode changes. Focus starts on the close control, or the safe "Keep reservation"
  action for cancellation.
- Escape, the close action and a background click dismiss the dialog. Focus
  returns to the opener if it still exists; body scrolling is restored.
- Focus indicators remain visible, and reduced-motion preferences disable modal
  entrance animations.
- Management/cancellation errors appear inside the dialog, where they remain
  accessible while the page behind it is inert.

Closing a dialog does not cancel an already submitted network request. Existing
booking and authentication service behavior is unchanged. The wrapper is mounted
only while open; it uses a portal so page stacking contexts do not clip it.

Chromium tests cover focus containment, reverse/forward tabbing, background
inertness, Escape, explicit/backdrop closing, reopening, login/signup switching,
mobile access, safe cancellation focus and the reschedule dialog. Existing
storefront/password-visibility browser tests provide regression coverage. jsdom
tests use an open/close shim and do not prove browser focus behavior.

Other P1 work remains: Serbian copy consistency, page/share metadata, performance
and a broader keyboard/screen-reader review of drawers and nonmodal flows.
Manual assistive-technology and cross-browser acceptance remain necessary.
