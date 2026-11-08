from datetime import datetime, timezone
from fractions import Fraction


def _parse(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO 8601 string")
    s = value.strip()
    if not s:
        raise ValueError(f"{name} must not be empty")
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} is not a valid ISO 8601 datetime") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset or Z")
    if dt.microsecond != 0:
        raise ValueError(f"{name} must be second-precision")
    return dt.astimezone(timezone.utc)


def _cents(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int number of cents")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def prorate(period_start: str, period_end: str, effective_at: str,
            old_cents: int, new_cents: int) -> dict:
    start = _parse(period_start, "period_start")
    end = _parse(period_end, "period_end")
    eff = _parse(effective_at, "effective_at")
    old_cents = _cents(old_cents, "old_cents")
    new_cents = _cents(new_cents, "new_cents")

    if end <= start:
        raise ValueError("period_end must be strictly later than period_start")
    if eff < start or eff > end:
        raise ValueError("effective_at must lie within the billing period")

    total_td = end - start
    remaining_td = end - eff
    if total_td.microseconds or remaining_td.microseconds:
        raise ValueError("datetimes must be second-precision")
    total_seconds = total_td.days * 86400 + total_td.seconds
    remaining_seconds = remaining_td.days * 86400 + remaining_td.seconds
    elapsed_seconds = total_seconds - remaining_seconds

    exact = Fraction(old_cents * elapsed_seconds + new_cents * remaining_seconds,
                     total_seconds)
    charge = round(exact)  # Fraction.__round__ uses round-half-even

    return {
        "charge_cents": int(charge),
        "total_seconds": int(total_seconds),
        "remaining_seconds": int(remaining_seconds),
    }
