from datetime import datetime, timedelta, timezone

_ONE_SECOND = timedelta(seconds=1)


def _parse_instant(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO 8601 string")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid ISO 8601 datetime: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset or Z")
    if dt.microsecond != 0:
        raise ValueError(f"{name} must have second precision (microseconds zero)")
    # Normalise to UTC so the difference between instants is exact.
    return dt.astimezone(timezone.utc)


def _validate_cents(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int number of cents")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _round_half_even(numerator, denominator):
    # denominator is positive; exact integer rounding, ties to even.
    q, r = divmod(numerator, denominator)
    twice = 2 * r
    if twice > denominator or (twice == denominator and q % 2 == 1):
        q += 1
    return q


def prorate(period_start: str, period_end: str, effective_at: str, old_cents: int, new_cents: int) -> dict:
    start = _parse_instant(period_start, "period_start")
    end = _parse_instant(period_end, "period_end")
    effective = _parse_instant(effective_at, "effective_at")

    old = _validate_cents(old_cents, "old_cents")
    new = _validate_cents(new_cents, "new_cents")

    if end <= start:
        raise ValueError("period_end must be strictly later than period_start")
    if effective < start or effective > end:
        raise ValueError("effective_at must lie within [period_start, period_end]")

    total_seconds = (end - start) // _ONE_SECOND
    remaining_seconds = (end - effective) // _ONE_SECOND
    elapsed_seconds = total_seconds - remaining_seconds

    numerator = old * elapsed_seconds + new * remaining_seconds
    charge = _round_half_even(numerator, total_seconds)

    return {
        "charge_cents": charge,
        "total_seconds": total_seconds,
        "remaining_seconds": remaining_seconds,
    }
