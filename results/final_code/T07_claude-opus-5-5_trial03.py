from datetime import datetime, timezone
from fractions import Fraction


def _parse(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("datetime must be a non-empty ISO 8601 string")
    s = value.strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid ISO 8601 datetime: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"datetime must include a timezone offset: {value!r}")
    if dt.microsecond != 0:
        raise ValueError(f"datetime must be second precision: {value!r}")
    return dt.astimezone(timezone.utc)


def _cents(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def prorate(period_start: str, period_end: str, effective_at: str,
            old_cents: int, new_cents: int) -> dict:
    start = _parse(period_start)
    end = _parse(period_end)
    eff = _parse(effective_at)
    old_cents = _cents(old_cents, "old_cents")
    new_cents = _cents(new_cents, "new_cents")

    if end <= start:
        raise ValueError("period_end must be strictly later than period_start")
    if eff < start or eff > end:
        raise ValueError("effective_at must lie within the period")

    total = (end - start).days * 86400 + (end - start).seconds
    remaining = (end - eff).days * 86400 + (end - eff).seconds
    elapsed = total - remaining

    exact = Fraction(old_cents * elapsed + new_cents * remaining, total)
    charge = round(exact)  # Fraction.__round__ uses round-half-even

    return {
        "charge_cents": int(charge),
        "total_seconds": int(total),
        "remaining_seconds": int(remaining),
    }
