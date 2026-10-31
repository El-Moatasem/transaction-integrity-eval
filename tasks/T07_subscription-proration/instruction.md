# T07: UTC-aware subscription proration

## Business relevance
Billing changes during a period must account for exact elapsed time, timezone offsets, and well-defined half-open boundaries.

## Requirements
Implement `prorate(period_start: str, period_end: str, effective_at: str, old_cents: int, new_cents: int) -> dict`. Times are ISO 8601 strings WITH timezone offsets or Z; parse and compare as UTC instants. Period is half-open [period_start,period_end); effective_at can equal either endpoint. All three datetimes must be second-precision (microseconds zero); period_end must be strictly later than period_start. Both rate values must be nonnegative int cents and not bool. Compute exact total_seconds and remaining_seconds. The full-period charge equals `old_cents * elapsed_seconds / total_seconds + new_cents * remaining_seconds / total_seconds`, rounded ONCE to the nearest integer cent using ROUND_HALF_EVEN (not the sum of separately rounded components). Return exactly {"charge_cents": int, "total_seconds": int,"remaining_seconds": int}. Invalid inputs raise ValueError. Real seconds elapsed, not calendar day counts, determine proration; do not use the local machine timezone.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
