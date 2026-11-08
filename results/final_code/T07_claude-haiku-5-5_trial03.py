from datetime import datetime, timedelta, timezone

_ONE_SECOND = timedelta(seconds=1)


def _parse_instant(value, name):
    """Parse an ISO 8601 string with an explicit offset or Z into an aware UTC datetime."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid ISO 8601 datetime: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset or Z")
    if dt.microsecond != 0:
        raise ValueError(f"{name} must have second precision (microseconds must be zero)")
    return dt.astimezone(timezone.utc)


def _validate_cents(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def prorate(period_start: str, period_end: str, effective_at: str, old_cents: int, new_cents: int) -> dict:
    start = _parse_instant(period_start, "period_start")
    end = _parse_instant(period_end, "period_end")
    effective = _parse_instant(effective_at, "effective_at")
    old_cents = _validate_cents(old_cents, "old_cents")
    new_cents = _validate_cents(new_cents, "new_cents")

    if end <= start:
        raise ValueError("period_end must be strictly later than period_start")
    if effective < start or effective > end:
        raise ValueError("effective_at must lie within [period_start, period_end]")

    # Exact integer seconds (microseconds are zero, so timedelta maps exactly).
    total_seconds = (end - start) // _ONE_SECOND
    elapsed_seconds = (effective - start) // _ONE_SECOND
    remaining_seconds = (end - effective) // _ONE_SECOND

    # charge = (old*elapsed + new*remaining) / total, rounded once, half-even.
    numerator = old_cents * elapsed_seconds + new_cents * remaining_seconds
    quotient, remainder = divmod(numerator, total_seconds)
    twice_remainder = 2 * remainder
    if twice_remainder > total_seconds or (twice_remainder == total_seconds and quotient % 2 == 1):
        quotient += 1

    return {
        "charge_cents": quotient,
        "total_seconds": total_seconds,
        "remaining_seconds": remaining_seconds,
    }
