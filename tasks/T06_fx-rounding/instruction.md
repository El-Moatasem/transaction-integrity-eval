# T06: FX conversion and currency-specific precision

## Business relevance
Float arithmetic, unsupported currencies, and one-size-fits-all cent rounding can misstate international payments.

## Requirements
Implement `convert(amount: str, source: str, target: str, rate: str) -> dict`. All monetary inputs and rates are decimal STRINGS (never floats). Currencies and minor-unit scales: USD=2, EUR=2, JPY=0, KWD=3. `amount` must represent a positive finite amount exactly expressible in the SOURCE minor units, allowing additional trailing zeros; `rate` must be a positive finite decimal. Reject unknown currencies, numeric rather than string inputs, negative/zero amounts or rates, and fractional source minor units with ValueError. Compute target value using exact decimal arithmetic `Decimal(amount) * Decimal(rate)`; round once to the TARGET minor-unit scale using ROUND_HALF_EVEN. Return exactly {"target_minor": int, "target_amount": fixed-width decimal str, "rate": unchanged rate str}. Example: USD 1.01 at rate 0.5 to USD gives 0.50, 50 minor units (banker's rounding). No network access or FX lookup; caller-supplied rate is authoritative.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
