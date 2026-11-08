from datetime import datetime, timezone


def _parse(s):
    if not isinstance(s, str):
        raise ValueError("datetime must be a string")
    try:
        d = datetime.fromisoformat(s)
    except (ValueError, TypeError) as ex:
        raise ValueError("invalid datetime") from ex
    if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
        raise ValueError("timezone offset required")
    if d.microsecond != 0:
        raise ValueError("microseconds not allowed")
    return d.astimezone(timezone.utc)


def _cents(v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ValueError("rate must be a nonnegative int")
    return v


def prorate(period_start, period_end, effective_at, old_cents, new_cents):
    a = _parse(period_start)
    b = _parse(period_end)
    e = _parse(effective_at)
    old_cents = _cents(old_cents)
    new_cents = _cents(new_cents)
    if b <= a:
        raise ValueError("period_end must be after period_start")
    if e < a or e > b:
        raise ValueError("effective_at outside period")
    total = int((b - a).total_seconds())
    remaining = int((b - e).total_seconds())
    elapsed = total - remaining
    num = old_cents * elapsed + new_cents * remaining
    q, r = divmod(num, total)
    if 2 * r > total or (2 * r == total and q % 2 == 1):
        q += 1
    return {"charge_cents": q, "total_seconds": total, "remaining_seconds": remaining}
