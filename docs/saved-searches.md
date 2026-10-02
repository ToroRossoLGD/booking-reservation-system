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

## Account searches

Signed-in visitors can open **Pretrage na nalogu** to load up to ten searches
stored privately on their account. They can save the current filters, rename
matching searches, remove entries and refresh changes made on another device.
Account searches are kept only in component memory on the client, not copied
into shared browser storage. Switching authentication tokens clears that state.

Local searches remain separate. Each local entry has an explicit transfer
button; no automatic upload takes place and transfer does not remove the local
copy. A matching account search disables the transfer button to preserve its
existing name. Refresh the account list to see another device's changes.

Authenticated `GET /saved-searches`, `PUT /saved-searches` (`name`, `path`) and
`DELETE /saved-searches/{id}` are scoped to the current user. PUT normalizes
supported filters, drops pagination and unknown parameters, and upserts the
same filter set. A user row lock serializes upserts and the ten-entry limit;
deleting an absent or another user's ID is an idempotent no-op. Invalid filter
values and external paths are rejected. Database uniqueness protects user/path
pairs, and deleting an account cascades to its searches.

Deploy migration `dab68421357e` using `alembic upgrade head`. Existing local
searches are unaffected. Matching-new-listing alerts and notification
preferences remain planned; neither local nor account saves send notifications.
