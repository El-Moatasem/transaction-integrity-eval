from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, Context, Inexact

CURRENCY_SCALES = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}


def _parse_positive_decimal(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a decimal string")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{name} is not a valid decimal: {value!r}")
    if not d.is_finite():
        raise ValueError(f"{name} must be finite")
    if d <= 0:
        raise ValueError(f"{name} must be positive")
    return d


def _scale(currency, name):
    if not isinstance(currency, str) or currency not in CURRENCY_SCALES:
        raise ValueError(f"unsupported {name} currency: {currency!r}")
    return CURRENCY_SCALES[currency]


def convert(amount, source, target, rate):
    source_scale = _scale(source, "source")
    target_scale = _scale(target, "target")
    a = _parse_positive_decimal(amount, "amount")
    r = _parse_positive_decimal(rate, "rate")

    # Exact arithmetic context: enough precision that nothing rounds implicitly.
    prec = len(a.as_tuple().digits) + len(r.as_tuple().digits) + 64
    prec += abs(a.as_tuple().exponent) + abs(r.as_tuple().exponent)
    ctx = Context(prec=prec, rounding=ROUND_HALF_EVEN, traps=[InvalidOperation, Inexact],
                  Emax=999999999, Emin=-999999999)

    # Source amount must be exactly expressible in source minor units.
    source_quantum = Decimal(1).scaleb(-source_scale)
    try:
        a.quantize(source_quantum, context=ctx)
    except (Inexact, InvalidOperation):
        raise ValueError(
            f"amount {amount!r} has fractional {source} minor units"
        )

    product = ctx.multiply(a, r)  # exact (Inexact trapped)

    target_quantum = Decimal(1).scaleb(-target_scale)
    round_ctx = Context(prec=prec, rounding=ROUND_HALF_EVEN, traps=[InvalidOperation],
                        Emax=999999999, Emin=-999999999)
    target_value = product.quantize(target_quantum, rounding=ROUND_HALF_EVEN, context=round_ctx)
    target_minor = int(target_value.scaleb(target_scale, context=round_ctx))

    return {
        "target_minor": target_minor,
        "target_amount": format(target_value, "f"),
        "rate": rate,
    }
