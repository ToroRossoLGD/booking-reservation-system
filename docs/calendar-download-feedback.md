# Calendar download feedback

The shared calendar button announces when an ICS download has been initiated and
explains that the user must open the file in a calendar app. It does not claim the
file was saved or imported, because the browser cannot confirm those actions.

If the event is no longer exportable, a Serbian alert asks the user to refresh and
check confirmation status. Generation/browser errors retain explicit retry. Each
attempt replaces prior feedback; no automatic download or external calendar sync
is introduced. Existing file content, filenames and object-URL cleanup are unchanged.

Component tests cover successful initiation, unavailable events, failed downloads,
retry, changing availability and resource cleanup. This is a P1 feedback improvement,
not the P2 external calendar synchronization feature. No migration is required.
