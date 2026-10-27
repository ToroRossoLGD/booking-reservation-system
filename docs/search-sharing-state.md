# Search sharing state

Copy feedback belongs to the exact search path supplied by the catalog. Changing
filters or pagination clears the previous copied message and manual fallback.
An old clipboard operation may still complete, but it cannot report success or
failure for the replacement search. Copying the new search requires an explicit
click. The active copy button displays a busy state and blocks duplicate attempts.

Component tests cover pending copies across filter changes, duplicate clicks,
successful-copy reset and manual fallback reset. Clipboard contents cannot be
cancelled after a browser write has started; the UI therefore makes no claim that
a new search was copied until its own request completes. No migration is required.
