# T12: Partial refund ceiling and replay

## Business relevance
Refunds may arrive in installments and may be retried; their sum must never exceed a captured payment.

## Requirements
Implement `setup(conn)` and `refund(conn, capture_id: str, refund_key: str, amount_cents: int) -> dict` in service.py. `setup` creates captures(capture_id TEXT PRIMARY KEY, account_id TEXT, amount_cents INTEGER), balances(account_id TEXT PRIMARY KEY, available_cents INTEGER), refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT). Tests seed valid captures and balances. `capture_id` and `refund_key` must be nonempty strings. New refund must be positive integer cents (bool invalid), existing capture and balance, and must not exceed the captured amount when added to all earlier refunds for the same capture. Add the refund amount to available_cents and persist the refund receipt `ref_{refund_key}`. The total of committed refunds for a capture must never exceed the captured amount, and every committed refund receipt must correspond to exactly one credit of its amount to available_cents, and no credit may exist without its receipt. Same refund key with identical capture/amount replays without changes; changed payload raises ValueError. Return exactly {"receipt_id": ...,"capture_id": ...,"amount_cents": ...,"status":"refunded"}. Invalid attempts leave database unchanged. Unexpected SQLite database errors (such as a failing constraint or trigger) must leave no changes and propagate as SQLite database exceptions, not be converted to ValueError.

Deployment: This service runs on several worker processes; each call uses its own SQLite connection. sqlite3.OperationalError is acceptable if the database is busy, provided the call leaves no partial changes; a later retry must still replay correctly and preserve every rule above. Calls must not block indefinitely.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
