# Account roles and operator provisioning

Public `POST /auth/register` creates customers only. An omitted role or explicit `customer` is accepted; `owner`, `admin` and unknown fields are rejected with 422. The registration service also hard-codes the customer role so bypassing schema validation cannot grant privileges. Google signup continues to create customers.

Owner/admin provisioning is a trusted operator operation, not a public API. An authorized operator with shell access and the target database credentials must verify the person's identity and authorization before changing a role. Do not give visitors shell access or database credentials.

## Provision an existing account

1. Have the person register normally. Confirm their account ID and exact stored email through a trusted administrative/database session.
2. Use the deployment environment for the intended database. Apply the existing migrations before running the command. No new migration is required for this feature.
3. Preview the change (no writes):

```bash
python -m app.provision_user --user-id 42 --email owner@example.com --expected-role customer --role owner
```

4. After verifying the target, repeat with `--apply`:

```bash
python -m app.provision_user --user-id 42 --email owner@example.com --expected-role customer --role owner --apply
```

Use `--role admin` for an approved administrator, including the first administrator. This requires no existing admin account because authorization is the operator's trusted shell/database access. To remove privileges, use the current role as `--expected-role` and target `customer`.

The command locks the user row and requires both ID/email and the expected current role to match. A repeated command with an outdated expected role fails rather than overwriting a newer decision. Requesting the already assigned role is a no-op. The command does not create users, change passwords, transfer listings or delete existing business records.

An applied role change increments the account's token version and revokes its active API keys in the same transaction. The user must sign in again and create replacement API keys if needed. This prevents an old key or bearer session from silently gaining new permissions. Requests already in flight are not retroactively cancelled.

Successful output is JSON containing user ID, previous/target role, whether a change was applied and a UTC timestamp. Retain that output in a protected operator change log together with the approving operator and reason. This is an operational log, not a database-backed or tamper-proof audit trail. No password, token or database URL is printed. A database failure causes a nonzero exit and transaction rollback; inspect the account's current state before retrying if connection loss made the commit outcome uncertain.

## Existing installations

This release does not automatically downgrade existing owners or administrators: legitimate privileged accounts cannot be distinguished from unapproved ones without an operator review. If registration was internet-accessible before this fix, keep access restricted while reviewing all privileged accounts and relevant activity. Demote unapproved accounts with the command and review their listings, keys and other changes. Rotate compromised credentials through the operational recovery process if exposure is confirmed.

The new registration rule does not implement email verification, rate limiting, production deployment or a self-service owner approval UI. Those remain separate roadmap items. Do not mark an existing deployment reviewed merely because this code was deployed.
