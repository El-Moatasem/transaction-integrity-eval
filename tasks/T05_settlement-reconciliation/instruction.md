# T05: Settlement reconciliation with duplicates

## Business relevance
Duplicate or missing settlement records can silently hide financial differences unless both sources are reconciled as multisets.

## Requirements
Implement `reconcile(ledger: list[dict], settlement: list[dict])->dict` in service.py. Ledger rows: {"transaction_id":str,"status":"settled"|"pending","gross_cents":int,"fee_cents":int}. Settlement rows: {"transaction_id":str,"net_cents":int}. IDs are nonempty strings and values are nonnegative ints (inputs otherwise valid). For repeated IDs in either source, the FIRST occurrence is authoritative; report each duplicated ID once as {"source":"ledger"|"settlement","transaction_id":id}, sorted by source then ID. Only unique ledger IDs with status settled contribute expected net = gross_cents-fee_cents (data guarantees gross >= fee). Missing is sorted settled ledger IDs with no settlement record. Unexpected is sorted settlement IDs whose ledger ID is missing or pending. A mismatch exists only when a settled ledger ID has a settlement record and differing net_cents; output {"transaction_id":id,"expected_cents":int,"received_cents":int} sorted by ID. `expected_total_cents` sums first-occurrence settled ledger nets. `received_total_cents` sums first-occurrence settlement amounts, INCLUDING unexpected records. Output exact keys: duplicates (list), missing (list[str]), unexpected (list[str]), amount_mismatches (list[dict]), expected_total_cents (int), received_total_cents (int). Do not mutate inputs; use only standard library.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
