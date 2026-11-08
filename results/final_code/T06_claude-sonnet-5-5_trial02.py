from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext

SCALES = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}


def _dec(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    s = value.strip()
    if not s or s != value:
        raise ValueError(f"invalid {name}")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"invalid {name}")
    if not d.is_finite() or d <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return d


def convert(amount: str, source: str, target: str, rate: str) -> dict:
    if not isinstance(source, str) or not isinstance(target, str):
        raise ValueError("currency must be a string")
    if source not in SCALES or target not in SCALES:
        raise ValueError("unknown currency")
    amt = _dec(amount, "amount")
    r = _dec(rate, "rate")
    ss, ts = SCALES[source], SCALES[target]

    with localcontext() as ctx:
        ctx.prec = max(ctx.prec, 200 + len(amount) + len(rate))
        ctx.traps[InvalidOperation] = True
        if amt.scaleb(ss) != amt.scaleb(ss).to_integral_value():
            raise ValueError("fractional source minor units")
        value = amt * r
        minor = int(value.scaleb(ts).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
        text = str(Decimal(minor).scaleb(-ts).quantize(Decimal(1).scaleb(-ts)))
        if "E" in text or "e" in text:
            text = format(Decimal(minor).scaleb(-ts).quantize(Decimal(1).scaleb(-ts)), "f")
    return {"target_minor": minor, "target_amount": text, "rate": rate}
