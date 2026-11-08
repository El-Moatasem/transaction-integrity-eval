import re
from decimal import Decimal, Context, ROUND_HALF_EVEN, InvalidOperation

SCALES = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
_NUM = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")
_CTX = Context(prec=5000, rounding=ROUND_HALF_EVEN, Emax=100000, Emin=-100000)


def _parse(value, name):
    if not isinstance(value, str) or not _NUM.fullmatch(value):
        raise ValueError(f"invalid {name}")
    try:
        d = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"invalid {name}")
    if not d.is_finite() or d <= 0:
        raise ValueError(f"{name} must be positive and finite")
    if abs(d.adjusted()) > 1000 or -d.as_tuple().exponent > 1000:
        raise ValueError(f"{name} out of range")
    return d


def convert(amount, source, target, rate):
    if not isinstance(source, str) or not isinstance(target, str):
        raise ValueError("invalid currency")
    if source not in SCALES or target not in SCALES:
        raise ValueError("unknown currency")
    amt = _parse(amount, "amount")
    rt = _parse(rate, "rate")
    ss = SCALES[source]
    if amt != amt.quantize(Decimal(1).scaleb(-ss), context=_CTX):
        raise ValueError("fractional source minor units")
    ts = SCALES[target]
    exp = Decimal(1).scaleb(-ts)
    value = _CTX.multiply(amt, rt)
    q = value.quantize(exp, rounding=ROUND_HALF_EVEN, context=_CTX)
    minor = int(q.scaleb(ts, context=_CTX))
    return {"target_minor": minor, "target_amount": format(q, "f"), "rate": rate}
