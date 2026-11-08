import re
from decimal import Decimal, Context, ROUND_HALF_EVEN, InvalidOperation, Inexact

SCALES = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
_DEC = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\Z")


def _parse(value, name):
    if not isinstance(value, str) or not _DEC.match(value):
        raise ValueError(f"invalid {name}")
    try:
        d = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"invalid {name}")
    if not d.is_finite() or d <= 0:
        raise ValueError(f"invalid {name}")
    return d


def convert(amount, source, target, rate):
    if not isinstance(source, str) or not isinstance(target, str):
        raise ValueError("invalid currency")
    if source not in SCALES or target not in SCALES:
        raise ValueError("unknown currency")
    amt = _parse(amount, "amount")
    r = _parse(rate, "rate")
    if amt != amt.quantize(Decimal(1).scaleb(-SCALES[source]), context=Context(prec=100000)):
        raise ValueError("fractional source minor units")
    ctx = Context(prec=100000, Emax=999999999, Emin=-999999999)
    value = ctx.multiply(amt, r)
    q = Decimal(1).scaleb(-SCALES[target])
    rounded = value.quantize(q, rounding=ROUND_HALF_EVEN, context=ctx)
    minor = int(rounded.scaleb(SCALES[target]))
    return {
        "target_minor": minor,
        "target_amount": f"{rounded:.{SCALES[target]}f}",
        "rate": rate,
    }
