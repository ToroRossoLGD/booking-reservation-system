# Listing sharing recovery

On a public listing page, clipboard or system-share failures display a Serbian
message and focus a read-only field with the whole listing URL selected. Users
can copy it with their keyboard or the browser's context menu. The message is
associated with the field for screen readers, and repeated failures restore focus.

The shared URL contains only the origin and listing path, without query parameters
or fragments. Cancelling the system share sheet is not an error. A successful
clipboard retry removes the fallback and announces that the link was copied.

Desktop/mobile browser tests mock clipboard denial and system-share failure,
verify cancellation, selection and clean URLs, and exercise successful retry.
Existing listing/inquiry browser tests remain regression coverage. No API changes
or migration are required; native operating-system share sheets still need manual
device acceptance as part of the wider P1 UX review.
