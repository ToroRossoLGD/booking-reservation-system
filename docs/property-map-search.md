# Property map search

Visitors can open **Prikaži mapu** on the property search page. This initially restricts results to listings with an owner-selected public location. Move or zoom the map and choose **Pretraži ovaj deo mape** to search that area. Moving the map alone does not issue a search.

The map and list use the same paginated result set (12 listings per page), ordering and filters. Coincident locations share a marker whose popup lists every matching listing on that page. **Prikaži lokacije ove stranice** fits the current page's markers; use the normal pagination controls for other results. The displayed total counts all matches, not just visible markers.

City, offer, currency, property details and short-stay availability filters continue to apply. For selected stay dates, popups show the server-calculated stay total and carry the dates and guest count to the listing page. Without dates, nightly prices are base prices. Neither a marker nor a matching search reserves inventory.

Map bounds are included in shared URLs, browser history and local/account saved searches. Saved-search alerts apply the same bounds to newly published listings. **Sakrij mapu** hides the visualization while keeping filters; **Ukloni ograničenje mape** removes only the map filter, and **Obriši filtere** clears all filters. Opening a URL with map bounds filters the list but does not load map tiles until the map is opened.

## Owner-controlled approximate location

In the listing editor, enable **Prikaži približnu lokaciju na javnoj mapi** and choose a point on the optional map or enter coordinates. Both coordinates are required when enabled. The same location setting is available for short stays, rentals and sales.

The API rounds each coordinate to two decimal places before saving. Only this public approximate point is stored in `property_listings`; no exact-coordinate copy is kept by this feature. A 0.01-degree latitude step is about 1.1 km; longitude distance varies with latitude. This is a coarse grid, not a guaranteed anonymity radius. The point may differ from the entrance, and an owner should choose an appropriate neighborhood location.

Existing listings default to no map location. Coordinates are never inferred from venue addresses, existing venue coordinates, IP addresses or device geolocation. Unchecking the option and saving sends both coordinates as null and removes the listing from map-filtered results. Ordinary text search can still return it. Drafts, withdrawn listings and moderation-suspended listings do not enter public map results. Existing owner/admin edit authorization applies.

This feature does not change the legacy venue directory or remove location clues that owners place in descriptions, photos or contact information. It also cannot revoke copies of previously published coordinates already obtained by visitors. Exact addresses should be shared privately when needed.

## API and deployment

`PropertyListingWrite` and listing responses have nullable `map_latitude` and `map_longitude`. Values must be a finite pair in latitude range -85 to 85 and longitude range -180 to 180. Sending neither field (or both null) clears the location in the existing full-replacement PUT contract.

`GET /properties` accepts:

| Parameter | Meaning |
| --- | --- |
| `map_only=true` | Only listings with a public approximate point |
| `map_south`, `map_north` | Inclusive latitude limits |
| `map_west`, `map_east` | Inclusive longitude limits |

Bounds must be supplied together, finite and ordered (`south < north`, `west < east`). Bounds imply location filtering even without `map_only`. Antimeridian-crossing rectangles are not supported. Invalid API queries return 422. Filtering uses the stored public point and happens before count, pagination and availability pricing; it never tests an undisclosed exact coordinate.

Run `alembic upgrade head` before deploying the API and frontend. Revision `c3fb39768023` adds nullable coordinate columns, a pair/range constraint and a coordinate index. Downgrade deletes the optional location settings; it retains listings and reservations. No geocoding keys or background workers are needed.

## Map provider and accessibility

Leaflet loads OpenStreetMap standard raster tiles only while a map is open. Visitors are told which provider is used before opening it. Tile requests disclose normal connection information (including IP address) and the viewed tile area to that provider. No address lookup or browser-location permission is requested. The owner picker also loads tiles only after an explicit click.

Visible attribution is retained, normal browser caching is used, and there is no tile prefetching or offline download feature. Follow the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/) when deploying: preserve the browser Referer header and switch to a suitable provider if traffic exceeds the community service's capacity. Tile availability is best effort. If tiles fail, the app shows a retry action and the searchable listing remains usable.

The ordinary listing provides a text alternative to the map. Map markers are keyboard focusable and open listing links; owner coordinates can be entered without using the map. Desktop/mobile browser tests cover marker grouping, safe popup text, bounds, pagination, history restoration, tile failure/retry and owner opt-in/removal. Backend tests cover validation, stored precision, authorization, availability, seasonal prices, alert matching and migration rollback.
