# T03: Exact double-entry transfer posting

## Business relevance
Ledger posting must preserve exact cents and currency constraints; silent float rounding and unbalanced journal entries are unacceptable.

## Requirements
Implement `setup(conn)` and `post_transfer(conn, transfer_id: str, source: str, target: str, amount: str, currency: str)->dict`. `setup` creates accounts(account_id TEXT PRIMARY KEY,currency TEXT), transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER), entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side)). Tests seed accounts. Supported currencies are USD and EUR, both with two decimal minor units. `amount` MUST be a decimal string greater than zero with no more than two nonzero fractional decimal digits: '1', '1.2', '1.20', and '1.200' are valid because extra zeros do not change value; '1.201' is invalid. No floats. Both accounts must exist and have the supplied currency, and source != target. Atomically insert one transfer and exactly two postings: `debit` on source and `credit` on target, both for identical positive amount_minor. A matching retry with same transfer ID and all fields returns the prior receipt; conflicting reuses raise ValueError. Output exactly {"transfer_id": id, "amount_minor": int, "entry_count": 2}. All invalid calls leave the DB unchanged.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
