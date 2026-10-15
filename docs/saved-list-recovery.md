# Saved-list recovery

The `/saved` page offers **Osveži oglase** to retrieve current published listings
and prices after changes on another device or owner withdrawals.

If a later page becomes empty, the client requests the last possible page using
the current total. Each fallback strictly reduces the offset, including when all
listings disappear, so concurrent changes cannot cause an endless retry loop.
Network failures retain the retry action; an expired session retains the login link.

After user-triggered pagination, removal, refresh or retry completes, keyboard
focus moves to the persistent page heading. Initial loading does not steal focus.
Loading and totals use status announcements; errors use an alert. Existing
save/unsave behavior and the meaning of saved listings are unchanged.

Playwright covers withdrawal from page two, recovery to page one, refresh failure
and retry into an empty account, heading focus and desktop/mobile save flows.
No database migration or environment configuration is required. This is a slice
of P1 empty/error-state and keyboard usability, not completion of the whole UX review.
