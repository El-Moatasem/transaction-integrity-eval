# T01: Idempotent payment capture

## Business relevance
Retries and concurrent requests must never charge a customer twice or silently reuse a key for a different payment.

## Requirements
Implement `setup(conn)` and `capture(conn, key: str, account_id: str, amount_cents: int) -> dict` in `service.py` using Python 3.11 and SQLite. `setup` creates accounts(account_id TEXT PRIMARY KEY, balance_cents INTEGER NOT NULL) and captures(key TEXT PRIMARY KEY, account_id TEXT, amount_cents INTEGER, receipt_id TEXT); it must be safe to call repeatedly. Tests seed accounts after setup. On a new capture: key and account_id must be nonempty strings; amount_cents must be a positive int, not bool; account must exist and have sufficient balance. Atomically subtract amount and store a receipt with ID `cap_{key}`. Return exactly {"receipt_id": ..., "account_id": ..., "amount_cents": ..., "status": "captured"}. A repeat with same key, account and amount returns that receipt without a second debit. A key reused with different account or amount raises ValueError and makes no changes. Any invalid input or insufficient funds raises ValueError with no partial changes. Independent SQLite connections may attempt the same capture concurrently; preserve these invariants under concurrent use; no particular locking statement is required. Do not depend on external services or in-memory global state.

Concurrent use: each caller supplies an independent SQLite connection with a configured busy timeout. A call encountering an actual database-lock timeout may raise sqlite3.OperationalError without partial changes; a subsequent caller retry must preserve idempotency and all committed invariants. Avoid indefinite blocking.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
