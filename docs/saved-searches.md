# Saved searches

The marketplace lets visitors name and save the currently applied search.
Up to 10 searches are stored under `bookica_saved_searches_v1` in local storage.
No login or API change is required. Searches belong to the browser profile,
not the signed-in account; clearing browser data removes them.

Opening a saved search restores its city, offer, supported filters, sorting and
stay dates on the first page. The current result-page offset is not saved.
Results are fetched again from the API rather than cached with the search.
Dates are kept literally, so older stay dates may need editing before reuse.

Saving the same normalized filters again changes the name instead of creating
a duplicate. Names may contain up to 60 characters. Existing searches can be
removed individually. Changes made in another tab are reflected by storage
events; mutations read the latest stored list before writing it.

Stored paths are restricted to internal marketplace search URLs and normalized
through the existing filter parser. Unknown parameters are dropped, invalid
entries are ignored and malformed stored JSON is treated as an empty list.
Storage permission/quota errors are shown without reporting a successful save
or deleting entries from the visible list.

This is the local saved-search portion of the roadmap. Cross-device account
sync, matching-new-listing alerts and notification preferences remain planned.
