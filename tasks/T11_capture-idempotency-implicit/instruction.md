# T11: Idempotent payment capture

## Business relevance
A customer must never be charged twice for the same payment, and a key must never be silently reused for a different payment.

## Requirements
Implement `setup(conn)` and `capture(conn, key: str, account_id: str, amount_cents: int) -> dict` in `service.py` using Python 3.11 and SQLite. `setup` creates accounts(account_id TEXT PRIMARY KEY, balance_cents INTEGER NOT NULL) and captures(key TEXT PRIMARY KEY, account_id TEXT, amount_cents INTEGER, receipt_id TEXT); it must be safe to call repeatedly. Tests seed accounts after setup. On a new capture: key and account_id must be nonempty strings; amount_cents must be a positive int, not bool; account must exist and have sufficient balance. Subtract the amount and store a receipt with ID `cap_{key}`. A debit must never exist without its receipt, and a receipt must never exist without its debit. Return exactly {"receipt_id": ..., "account_id": ..., "amount_cents": ..., "status": "captured"}. A repeat with same key, account and amount returns that receipt without a second debit. An identical request must return the original receipt, never an IntegrityError. An account must never be debited twice for the same key. A key reused with different account or amount raises ValueError and makes no changes. Any invalid input or insufficient funds raises ValueError with no partial changes. Do not depend on external services or in-memory global state. Unexpected SQLite database errors (such as a failing constraint or trigger) must leave no changes and propagate as SQLite database exceptions, not be converted to ValueError.

Deployment: This service runs on several worker processes; each call uses its own SQLite connection. sqlite3.OperationalError is acceptable if the database is busy, provided the call leaves no partial changes; a later retry must still return the original receipt and preserve every rule above. Calls must not block indefinitely.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
