# Verification status refresh

The token-free `/verify-email` page offers **Proveri status potvrde**. This reads
the authenticated account again, allowing users to discover confirmation completed
in another tab, retry failed account loading, or detect an expired session without
reloading the page. It never sends or confirms an email on its own.

The refresh button remains mounted through loading and result changes, preserving
keyboard focus. It is disabled during loading or an email action. Successful status
updates use the existing status message; failures and guest states retain their
existing recovery guidance. Token-bearing confirmation links keep deliberate
confirmation and do not fetch account status.

Refreshing preserves the resend deadline. An unverified result cannot bypass the
cooldown; verified and guest results hide resend controls and stale countdowns.
No polling, cross-tab credential transfer or new credential storage is introduced.

Desktop/mobile tests cover failed loading, recovery, unchanged unverified status,
preserved cooldown, verification elsewhere, expired sessions and absence of email
side effects. Existing confirmation/rate-limit tests remain regression coverage.
No API changes, migrations or configuration are required. Real-provider delivery
and hosted acceptance remain open P1 items.
