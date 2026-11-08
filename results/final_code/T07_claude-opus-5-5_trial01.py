from datetime import datetime, timezone
from fractions import Fraction


def _parse(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO 8601 string")
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} is not a valid ISO 8601 datetime") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")
    if dt.microsecond != 0:
        raise ValueError(f"{name} must have second precision")
    return dt.astimezone(timezone.utc)


def _cents(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def prorate(period_start, period_end, effective_at, old_cents, new_cents):
    a = _parse(period_start, "period_start")
    b = _parse(period_end, "period_end")
    e = _parse(effective_at, "effective_at")
    old_cents = _cents(old_cents, "old_cents")
    new_cents = _cents(new_cents, "new_cents")

    if b <= a:
        raise ValueError("period_end must be strictly later than period_start")
    if e < a or e > b:
        raise ValueError("effective_at must lie within the period")

    total = (b - a)
    remaining = (b - e)
    # All values are whole seconds (microseconds validated as zero).
    total_seconds = total.days * 86400 + total.seconds
    remaining_seconds = remaining.days * 86400 + remaining.seconds
    elapsed_seconds = total_seconds - remaining_seconds

    exact = Fraction(old_cents * elapsed_seconds + new_cents * remaining_seconds,
                     total_seconds)
    charge = round(exact)  # Fraction.__round__ uses round-half-to-even

    return {
        "charge_cents": int(charge),
        "total_seconds": int(total_seconds),
        "remaining_seconds": int(remaining_seconds),
    }
