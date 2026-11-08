from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext, Inexact

MINOR_UNITS = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}


def _parse_positive_decimal(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a decimal string")
    if value != value.strip() or "_" in value or not value:
        raise ValueError(f"{name} is not a valid decimal string")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} is not a valid decimal string") from None
    if not d.is_finite():
        raise ValueError(f"{name} must be finite")
    if d <= 0:
        raise ValueError(f"{name} must be positive")
    return d


def _scale(currency, name):
    if not isinstance(currency, str) or currency not in MINOR_UNITS:
        raise ValueError(f"unsupported {name} currency: {currency!r}")
    return MINOR_UNITS[currency]


def convert(amount: str, source: str, target: str, rate: str) -> dict:
    src_scale = _scale(source, "source")
    tgt_scale = _scale(target, "target")
    amt = _parse_positive_decimal(amount, "amount")
    r = _parse_positive_decimal(rate, "rate")

    with localcontext() as ctx:
        # Enough precision for exact arithmetic; trap any inexact result.
        ctx.prec = max(
            100,
            len(amt.as_tuple().digits) + len(r.as_tuple().digits)
            + max(0, amt.adjusted()) + max(0, r.adjusted()) + 50,
        )
        ctx.Emax = 999999999
        ctx.Emin = -999999999
        ctx.traps[Inexact] = True

        # Amount must be exactly expressible in source minor units.
        src_quant = Decimal(1).scaleb(-src_scale)
        if amt.as_tuple().exponent < -src_scale:
            ctx.traps[Inexact] = False
            if amt.quantize(src_quant, rounding=ROUND_HALF_EVEN) != amt:
                raise ValueError("amount has fractional source minor units")
            ctx.traps[Inexact] = True

        product = amt * r  # exact
        ctx.traps[Inexact] = False
        tgt_quant = Decimal(1).scaleb(-tgt_scale)
        rounded = product.quantize(tgt_quant, rounding=ROUND_HALF_EVEN)
        minor = int(rounded.scaleb(tgt_scale))

    return {
        "target_minor": minor,
        "target_amount": f"{rounded:.{tgt_scale}f}",
        "rate": rate,
    }
