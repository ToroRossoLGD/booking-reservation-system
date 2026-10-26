# Rental inquiry message usability

Rental inquiries validate a trimmed message of 10–3000 Unicode code points before
sending. The form shows a character count and associated Serbian guidance, focuses
invalid input and keeps overlong pasted text editable. Date and duration fields
retain their native required/minimum/maximum validation.

Failed requests preserve the draft and reuse the request UUID for unchanged data.
Successful submission focuses confirmation. Unit and desktop/mobile browser tests
cover validation, retained input, retry and success focus. No migration or API
changes are required; this implements part of the P1 core UX review.
