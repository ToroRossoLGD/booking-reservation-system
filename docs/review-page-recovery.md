# Guest review navigation

Reviews load only when the guest opens the review section. Opening, pagination
and explicit retry move keyboard focus to the review heading once results or an
error arrive. Failed requests retain the requested offset for retry.

An empty later page returns to offset zero and explains the change in Serbian
after the first page loads. An empty first page shows the normal empty state and
stops recovery. Both pagination buttons are disabled when there are no reviews.

Desktop/mobile browser tests cover next/previous navigation, error focus, retry
and recovery to an empty first page. This is part of the P1 core UX review; no API
changes or database migration are required.
