from datetime import datetime, timezone


def _parse_instant(value, name):
    """Parse a second-precision ISO 8601 string with an explicit offset or Z into a UTC datetime."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO 8601 string")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid ISO 8601 datetime: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset or Z")
    if dt.microsecond != 0:
        raise ValueError(f"{name} must have second precision (microseconds must be zero)")
    return dt.astimezone(timezone.utc)


def _parse_cents(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int number of cents")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def prorate(period_start: str, period_end: str, effective_at: str, old_cents: int, new_cents: int) -> dict:
    start = _parse_instant(period_start, "period_start")
    end = _parse_instant(period_end, "period_end")
    effective = _parse_instant(effective_at, "effective_at")
    old = _parse_cents(old_cents, "old_cents")
    new = _parse_cents(new_cents, "new_cents")

    if end <= start:
        raise ValueError("period_end must be strictly later than period_start")
    if not (start <= effective <= end):
        raise ValueError("effective_at must fall within [period_start, period_end]")

    total = int((end - start).total_seconds())
    remaining = int((end - effective).total_seconds())
    elapsed = total - remaining

    # Exact rational charge: (old*elapsed + new*remaining) / total, rounded once
    # to the nearest integer cent with ROUND_HALF_EVEN, using integer arithmetic.
    numerator = old * elapsed + new * remaining
    q, r = divmod(numerator, total)
    if 2 * r > total or (2 * r == total and q % 2 == 1):
        q += 1
    return {
        "charge_cents": q,
        "total_seconds": total,
        "remaining_seconds": remaining,
    }
