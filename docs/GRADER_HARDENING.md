# Grader hardening backlog (not falsely claimed complete)

## Shared objective
Preserve committed financial state across concurrency, retries, reordering, and partial failures, without requiring a particular SQL statement. The evaluation tests observable invariants, not use of `BEGIN IMMEDIATE`.

## T02 concrete tests to add
1. Two concurrent refunds of 700 cents against a 1,000-cent captured payment: at most one may commit; retry after contention must be safe.
2. Use independent connections with a configured SQLite busy timeout and bounded threads/joins; a SQLITE_BUSY timeout is only acceptable when it leaves no partial writes.
3. Execute both orderings and a controlled read/write interleaving. The scheduler should release a paused correct writer before waiting on a blocked writer to prevent deadlock.
4. Verify ledger sum, account credit, and receipt count match for all committed attempts, even on a database-trigger-induced failure.
5. Check golden reference AND the separate counter-based atomic-update variant under the same grader. Do not require explicit lock syntax.
6. Construct a deliberately wrong read-then-write implementation and show the test rejects a violation; report limitations where SQLite naturally prevents corruption via busy errors.

## T01/T10 next
T01: duplicate same-key captures competing, conflicting payloads, balance debits exactly once, after-failure retry.
T10: failure between inbox, balance and outbox writes must roll back all three; duplicate event delivery across connections remains idempotent.

## Publication standard
Never infer 20/20 grader reliability from smoke tests. Maintain a positive/negative matrix and manually review valid alternative solutions and failure logs.
