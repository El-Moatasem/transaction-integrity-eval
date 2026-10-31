# T02: Partial refund ceiling and replay

## Business relevance
Refunds may arrive concurrently and in installments; the sum must never exceed a captured payment.

## Requirements
Implement `setup(conn)` and `refund(conn, capture_id: str, refund_key: str, amount_cents: int) -> dict` in service.py. `setup` creates captures(capture_id TEXT PRIMARY KEY, account_id TEXT, amount_cents INTEGER), balances(account_id TEXT PRIMARY KEY, available_cents INTEGER), refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT). Tests seed valid captures and balances. New refund must be positive integer cents (bool invalid), existing capture and balance, and must not exceed the captured amount when added to all earlier refunds for the same capture. Atomically add refund amount to available_cents and persist the refund receipt `ref_{refund_key}`. Same refund key with identical capture/amount replays without changes; changed payload raises ValueError. Return exactly {"receipt_id": ...,"capture_id": ...,"amount_cents": ...,"status":"refunded"}. Invalid attempts leave database unchanged. Independent connections may race; preserve the limit for every committed refund; any correct atomic strategy is acceptable.

Concurrent use: each caller supplies an independent SQLite connection with a configured busy timeout. A call encountering an actual database-lock timeout may raise sqlite3.OperationalError without partial changes; a subsequent caller retry must preserve idempotency and all committed invariants. Avoid indefinite blocking.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
