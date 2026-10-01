# Advance booking windows

Short-stay owners can set `advance_notice_days` (1–90, default 1) and
`booking_window_days` (2–365, default 365) in the listing editor.
Other offer types retain the defaults and do not use these rules.

Both limits use calendar dates in the property's timezone, not elapsed hours.
Arrival must be on or after today plus the notice. Departure must be on or
before today plus the window. Both boundaries are inclusive. For example,
on October 1 a notice of 3 and a window of 30 allow arrival from October 4
and departure through October 31. Minimum and maximum stay lengths still apply.
The window must accommodate the notice plus the minimum stay.

Availability search applies these limits before counting and pagination.
Quotes and confirmation enforce them on the server; confirmation reads the
latest listing under the existing transaction locks. Existing confirmed stays
are unchanged, and retries of a previously successful request return that stay.
The guest date controls and calendar indicate the configured window.

Deploy migration `be946209135c` with `alembic upgrade head`. Existing listings
receive defaults matching the previous tomorrow/365-day behavior. API clients
that omit the new fields on a full listing replacement use those defaults.

This feature does not introduce preparation gaps between stays or change
occupancy, cancellation, payment or seasonal pricing rules.
