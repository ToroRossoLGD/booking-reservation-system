# Guest review navigation

The stay-review form validates comments of 10–2000 trimmed Unicode code points
before submission. A character count and associated Serbian error explain the
limits; invalid comments receive keyboard focus. Pasted overlong text remains
editable, and the rating retains its native required selection. Existing retry
behavior preserves the comment after server errors. Unit and desktop/mobile
browser tests cover invalid comments, Unicode counts and successful publication.

Reviews load only when the guest opens the review section. Opening, pagination
and explicit retry move keyboard focus to the review heading once results or an
error arrive. Failed requests retain the requested offset for retry.

An empty later page returns to offset zero and explains the change in Serbian
after the first page loads. An empty first page shows the normal empty state and
stops recovery. Both pagination buttons are disabled when there are no reviews.

Desktop/mobile browser tests cover next/previous navigation, error focus, retry
and recovery to an empty first page. This is part of the P1 core UX review; no API
changes or database migration are required.
