# Property photos and galleries

Owners open **Fotografije** beside a saved listing in `/owner`. Select multiple
files and choose **Otpremi fotografije**. Each listing supports up to 12 photos;
the first is the cover. Use **Naslovna**, the arrow buttons or **Obriši** to change
the gallery. Deletion asks for confirmation. Removing the cover promotes the next
photo automatically; an empty gallery restores the illustration.

The catalog and saved listings show the cover thumbnail. Clicking it opens a
full-screen gallery with thumbnails, previous/next buttons and keyboard support
(left/right arrows and Escape). Focus returns to the cover on close. Broken images
show a fallback and a retry control. Photos are independent for each listing,
including multiple listings attached to the same venue.

## Uploads and storage

- Still JPEG, PNG and WebP images are accepted based on decoded content, not the
  filename or declared MIME type. SVG, animated images and damaged files are rejected.
- Limits: 12 photos per listing, 20 megapixels per image, and the smaller of
  `MEDIA_MAX_UPLOAD_BYTES` and 10 MiB. The UI allows selecting files up to 10 MiB.
- Pillow decodes and normalizes images: applies EXIF orientation, removes metadata
  (including GPS), composites transparency on white, and produces JPEGs of at most
  2560 pixels on the longest edge plus 640-pixel thumbnails. Original uploads are
  not retained. The [Pillow ImageOps documentation](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html)
  describes EXIF orientation handling.
- Uploads are sequential within a selected batch. Successful files leave the
  queue; failed and remaining files retain their request IDs for retries. Reloading
  the browser loses the local queue, so check the gallery before selecting again.
- The backend locks the listing while uploading, reordering or removing images.
  Repeating the same request ID and content returns the existing photo; different
  content with that ID returns 409. Reorder requests must contain every current
  photo exactly once, so stale lists cannot silently drop newly added photos.

## Deployment

1. Install updated `requirements.txt` (includes Pillow 12.3.0).
2. Run `alembic upgrade head`; revision `d49a6e0f1352` adds `property_photos` after
   `c38f5d9e0241`. No venue/resource media is imported or modified.
3. Create a **private** S3-compatible bucket and set `PROPERTY_PHOTO_BUCKET` to its
   name. Reuse the existing `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID` and
   `S3_SECRET_ACCESS_KEY` settings (or the runtime AWS credential provider).
   The service needs PutObject, GetObject and DeleteObject access to this bucket.
4. Keep anonymous access disabled. Do not reuse a publicly readable media bucket.
   `S3_PUBLIC_BASE_URL` is intentionally not used for property photos.

Docker Compose creates the separate `bookica-property-photos` MinIO bucket,
disables anonymous downloads, and configures the backend. The existing public
`bookica-media` bucket remains for the older venue/resource media system. The
browser does not need direct S3 access or S3 CORS configuration.

Images are served through the API. Public image requests require a currently
published listing; owner previews require the owner/admin account. The owner UI
fetches authenticated image blobs and releases browser object URLs when removed.
API responses never expose object keys and use `Cache-Control: private, no-store`
for images. Previously downloaded copies cannot be revoked by withdrawing a listing.
An unconfigured bucket returns 503 for uploads; existing text-only listings remain
usable without photo storage.

Storage and SQL cannot commit atomically. Failed uploads/SQL inserts attempt to
remove their uploaded objects. Deletion commits removal from the API before
deleting the two private objects, so a storage outage cannot leave deleted photos
publicly accessible. Cleanup failures are logged with the key for operational
reconciliation; this version has no automatic orphan cleanup job. Deleting a
parent listing/venue or downgrading the photo migration also requires reconciling
its storage objects; the foreign key removes database photo rows only.

## API

Property list/detail, owner listing and saved-list responses now include a
`photos` array (`id`, `property_id`, `position`, `width`, `height`), ordered cover
first. Lists fetch photo metadata in one batch.

- `GET /properties/{id}/photos/{photo_id}/image?thumbnail=true`: published image.
- `GET /owner/properties/{id}/photos`: owner/admin gallery metadata, including drafts.
- `GET /owner/properties/{id}/photos/{photo_id}/image?thumbnail=true`: authenticated preview.
- `POST /owner/properties/{id}/photos`: multipart `file` and UUID `request_id`.
- `PUT /owner/properties/{id}/photos/order`: `{ "photo_ids": [3, 1, 2] }`.
- `DELETE /owner/properties/{id}/photos/{photo_id}`: idempotent removal (204).

## Validation

`tests/test_property_photos.py` covers real image decoding, rotation, resize,
metadata removal, corrupt files, limits, permissions, request retries, cover order,
storage/SQL failure compensation, API image responses and migration round trips.
S3 is replaced with an in-memory adapter in these tests. CI enables the PostgreSQL
concurrent-upload limit test with `STAY_TEST_POSTGRES=1`.

`frontend/src/PropertyPhotos.test.tsx` covers gallery controls, image failures,
cover/delete actions, partial upload retries and limits. The Playwright
`property-photos.spec.ts` exercises upload, cover changes, fullscreen navigation,
Escape/focus behavior and deletion on desktop/mobile using API fixtures. A live
S3/MinIO smoke check is still needed when deploying storage credentials.
