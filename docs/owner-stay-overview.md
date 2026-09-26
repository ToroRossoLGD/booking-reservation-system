# Owner nightly reservation overview

At `/owner/stays`, owners can filter by listing and confirmed/cancelled status, or click **Danas dolaze** / **Danas odlaze** to see today's confirmed arrivals/departures. Changing filters resets pagination. **Osveži pregled** refreshes data; the dashboard does not automatically refresh at midnight.

The server applies filters before counts and pagination. Daily counts cover every confirmed reservation for the selected listing, regardless of the status/day filter or current page. Each reservation's saved timezone determines its local today. Daily results are ordered by saved local check-in/out time, unknown times last, then reservation ID. The listing dropdown includes all owned listings with reservation history, including unpublished ones. Multiple listings for one apartment remain separate filter choices, identified by listing ID.

Cards show status, agreed price, arrival/departure dates, saved time rules, guest count and contact, calendar download, and a shortcut to the listing's block manager. `/owner?blocks={property_id}` loads an authorized owner listing directly, so the shortcut works even if it is unpublished or not on the first listing page.

## API

`GET /owner/stays` accepts `property_id`, `status=confirmed|cancelled`, `day=arrivals|departures`, `offset`, and `limit`. Daily filters select confirmed stays; combining them with `status=cancelled` returns an empty page. The response extends the existing page with `arrivals_today`, `departures_today`, and `properties` (ID/title choices).

The query always restricts reservations and metadata to the current owner's venues. Admin overview follows the same owned-venue scope as before. `GET /owner/properties/{id}` requires owner/admin permissions and checks venue ownership (admins may access any listing, matching existing management permissions).

No database migration is needed. Deploy backend and frontend together. Guest reservation listing and cancellation keep their existing rules.
