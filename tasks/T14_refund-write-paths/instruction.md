# T14: Refund write paths

## Bug report
Finance reconciliation found customers who were refunded more than was captured. Fix the service.

## Requirements
`service.py` implements `setup(conn)`, `refund(conn, capture_id: str, refund_key: str, amount_cents: int) -> dict`, `adjust_capture(conn, capture_id: str, new_amount_cents: int) -> dict` and `void_remaining(conn, capture_id: str) -> dict` using Python 3.11 and SQLite. `setup` creates captures(capture_id TEXT PRIMARY KEY, account_id TEXT, amount_cents INTEGER, voided INTEGER NOT NULL DEFAULT 0), balances(account_id TEXT PRIMARY KEY, available_cents INTEGER) and refunds(refund_key TEXT PRIMARY KEY, capture_id TEXT, amount_cents INTEGER, receipt_id TEXT); it must be safe to call repeatedly. Tests seed captures (leaving `voided` at its default) and balances after setup.

Invariants, which hold for every function and every call:
- At every moment, the committed refunds for a capture never exceed its current captured amount.
- No refund commits after a void.
- Every committed refund receipt corresponds to exactly one credit of its amount to available_cents, and no credit exists without its receipt.
- A call that raises leaves the database unchanged.

`refund`: `capture_id` and `refund_key` must be nonempty strings, and `amount_cents` must be a positive int (bool invalid). A new refund requires an existing capture that is not voided and an existing balance row for the capture's account, and the refund added to all earlier refunds for the same capture must not exceed the capture's current amount_cents. It adds the amount to that account's available_cents and stores the receipt `ref_{refund_key}`. Return exactly {"receipt_id": ..., "capture_id": ..., "amount_cents": ..., "status": "refunded"}. A repeat with the same refund_key, capture_id and amount_cents returns the original receipt without changes, even after the capture was voided; the same refund_key with a different capture_id or amount raises ValueError. Every other invalid refund raises ValueError.

`adjust_capture`: lowers a capture's captured amount. `capture_id` must be a nonempty string and `new_amount_cents` a nonnegative int (bool invalid). The capture must exist and not be voided; `new_amount_cents` must not exceed the current amount_cents and must never be below the capture's committed refund total. It sets amount_cents to `new_amount_cents` and returns exactly {"capture_id": ..., "amount_cents": new_amount_cents, "status": "adjusted"}. Every violation raises ValueError.

`void_remaining`: voids the unrefunded remainder of a capture. `capture_id` must be a nonempty string naming an existing capture; otherwise ValueError. It sets voided=1 and returns exactly {"capture_id": ..., "status": "voided", "refunded_cents": R, "voided_cents": A - R}, where R is the capture's committed refund total and A its amount_cents. Because no refund may commit after a void, R remains the capture's refund total from then on. Voiding an already voided capture changes nothing and returns the same result. After a void, new refunds and adjustments for that capture raise ValueError.

Unexpected SQLite database errors (such as a failing constraint or trigger) must leave no changes and propagate as SQLite database exceptions, not be converted to ValueError.

Deployment: This service runs on several worker processes; each call uses its own SQLite connection. sqlite3.OperationalError is acceptable if the database is busy, provided the call leaves no partial changes; a later retry must still preserve every rule above. Calls must not block indefinitely. Do not depend on external services or in-memory global state.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
