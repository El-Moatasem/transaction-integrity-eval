from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction


def _parse(s):
    if not isinstance(s, str):
        raise ValueError("datetime must be a string")
    try:
        d = datetime.fromisoformat(s.strip())
    except (ValueError, TypeError):
        raise ValueError("invalid datetime")
    if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
        raise ValueError("timezone required")
    if d.microsecond != 0:
        raise ValueError("sub-second precision not allowed")
    return d.astimezone(timezone.utc)


def _rate(v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ValueError("invalid rate")
    return v


def prorate(period_start, period_end, effective_at, old_cents, new_cents):
    a = _parse(period_start)
    b = _parse(period_end)
    e = _parse(effective_at)
    old = _rate(old_cents)
    new = _rate(new_cents)
    if b <= a:
        raise ValueError("period_end must be after period_start")
    if e < a or e > b:
        raise ValueError("effective_at outside period")
    total = int((b - a).total_seconds())
    elapsed = int((e - a).total_seconds())
    remaining = total - elapsed
    frac = Fraction(old * elapsed + new * remaining, total)
    q, r = divmod(frac.numerator, frac.denominator)
    twice = 2 * r
    if twice > frac.denominator or (twice == frac.denominator and q % 2 == 1):
        q += 1
    return {"charge_cents": q, "total_seconds": total, "remaining_seconds": remaining}
