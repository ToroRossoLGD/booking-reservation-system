# Serbian account-access copy

The shared login/registration dialog now uses Serbian labels, instructions,
password-visibility controls, accessible names and submit/loading text. Header
login, registration and logout actions and the configured Google option match.
Registration copy describes property reservations and inquiries rather than only
the legacy hourly-space product.

Email-login/registration failures use controlled Serbian messages for invalid
credentials, existing accounts, forbidden access, input validation and service
failure. Rate-limit feedback preserves the localized retry duration. Unexpected
network/backend diagnostics are replaced with generic guidance. Errors are
announced through an alert inside the dialog; input and password-visibility reset
behavior remain unchanged. Email inputs advertise the email autocomplete hint.

Browser tests cover successful registration after a conflict, retained input,
login failure, desktop/mobile password visibility, keyboard focus, configured
Google navigation and the existing storefront flow. Unit tests cover controlled
error messages and retry durations. API contracts and account provisioning rules
are unchanged; this is not a new authentication system or full translation layer.

The broader P1 language review remains open: legacy dashboard/booking copy,
provider-return errors, other backend messages and remaining nonmodal flows still
need review. No migration or new configuration is required.
