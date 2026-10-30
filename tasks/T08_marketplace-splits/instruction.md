# T08: Deterministic largest-remainder payouts

## Business relevance
Rounding individual splits independently can create or destroy cents and make repeated allocation nondeterministic.

## Requirements
Implement `allocate(gross_cents: int, fee_cents: int, weights: dict[str,int]) -> dict`. gross_cents must be a positive int, fee_cents a nonnegative int <= gross, neither may be bool. weights is a nonempty dict of unique nonempty string seller IDs to positive integer weights (bool invalid). Distribute NET = gross_cents-fee_cents using Hamilton/largest-remainder apportionment entirely in integer arithmetic: each seller initially gets floor(net * weight / sum_weights). Assign remaining cents one at a time to sellers in descending order of integer remainder `(net*weight)%sum_weights`, ties broken by seller ID ascending in Unicode lexical order. Return exactly {"fee_cents":fee_cents,"allocations":{seller_id:int, ...},"payout_total_cents":net}, with allocation keys inserted in ascending seller ID order. Must conserve every cent, not mutate weights, and reject invalid inputs with ValueError.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
