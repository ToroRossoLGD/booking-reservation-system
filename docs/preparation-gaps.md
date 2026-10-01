# Preparation gaps

Short-stay owners can set `preparation_days` from 0 to 7; the default 0
preserves same-day guest turnover. Other offers must use 0.

The effective gap is the maximum among **booking-enabled short-stay listings
for the same venue**, including drafts and withdrawn listings. Disable booking
or lower the value on those listings to reduce that shared rule. A second
listing cannot bypass the apartment's preparation time.

For a two-day gap, a stay departing October 10 allows the next arrival on
October 12. A new stay preceding an October 10 arrival must depart by October 8.
These are calendar days, not 48-hour intervals; arrival/departure times do not
change the rule. The gap is applied once between stays, not twice.

Only confirmed reservations generate gaps. Cancellation frees the reservation
and its preparation days. Manual blocks retain their exact ranges; they do not
generate additional gaps. Owners can place a manual block inside preparation
time, which remains blocked until that manual block is removed.

Search filters before counting/pagination, quotes, confirmation and the public
calendar use the same shared rule. The calendar's `occupied` ranges include
preparation days and its `preparation_days` field reports the effective value.
Confirmation uses the existing venue lock to serialize competing bookings.

Changing the setting affects future booking attempts around existing stays;
it never moves or cancels previously confirmed reservations. It can therefore
leave existing stays closer together than the new rule permits. Successful
request retries still return the original stay. No preparation fee is added.

Deploy with `alembic upgrade head` (migration `cfa57310246d`). Existing rows
default to 0. Full listing replacement clients that omit the field use 0.
