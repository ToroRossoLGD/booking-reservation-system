# Sale inquiry usability

The purchase inquiry form validates a trimmed message of 10–3000 Unicode code
points before sending. It shows a character count, associates Serbian guidance
with the textarea and focuses invalid input. Overlong pasted text remains editable.
Successful submission focuses confirmation and its link to the buyer's inquiries.

Failed requests retain the message and reuse the request UUID for an unchanged
trimmed body, preserving existing idempotent retry behavior. Browser tests cover
empty, whitespace, short and overlong messages, Unicode counts, failed submission,
unchanged retry and success focus on desktop/mobile. Existing sales-flow tests
remain regression coverage. No API changes or migration are required.
