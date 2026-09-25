# Calendar downloads

Confirmed stays on `/stays` and `/owner/stays`, and confirmed viewings on
`/rentals` and `/owner/rentals`, offer **Dodaj u kalendar (.ics)**. Download the
file and import it into your calendar application. Proposed, closed or withdrawn
inquiries and cancelled stays do not offer an export.

- Stays use all-day dates from arrival up to, but excluding, checkout. Exact
  check-in/out times are not stored in Bookica and are not invented for export.
- Viewings use the confirmed instant converted to UTC, so the calendar can
  display it in the user's local timezone. No end time is included because the
  viewing workflow does not collect duration.
- Files include the listing title, booking/inquiry reference and a link back
  to the appropriate Bookica inbox. Stays also include the city. Private
  conversations, email addresses, guest identities and payment details are
  omitted. No invitations or email messages are sent.

This is a one-time export of the state currently shown on the page, not a
calendar subscription. Changes and cancellations in Bookica do not update an
imported file. Update or remove the event in your calendar after changing the
booking/viewing. Re-import behavior and duplicate handling depend on the calendar
client; stable event IDs do not guarantee automatic replacement.

The browser creates the file locally from data already returned by the existing
authorized APIs. No new API endpoint, public feed token, external calendar
connection, migration or configuration is introduced. The original hourly
platform's calendar subscriptions remain separate.

## Format and validation

Serialization follows [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545): CRLF
lines, UTF-8 folding at 75 octets, escaped TEXT values, UID/DTSTAMP, DATE values
for stays and UTC DATE-TIME values for viewings. `DTEND` is exclusive; a timed
event without an end time or duration has the same start/end instant.

Unit tests cover date semantics, offset conversion, status gating, stable IDs,
text escaping, Unicode folding and omission of private data. Browser tests
download and inspect actual files from all four guest/owner pages and check the
mobile layout. Imports into external calendar products are not automated here.
