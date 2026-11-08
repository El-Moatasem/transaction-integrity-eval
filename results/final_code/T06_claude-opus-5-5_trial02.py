import re
from decimal import Decimal, ROUND_HALF_EVEN, Context, InvalidOperation, localcontext

_SCALES = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
_DECIMAL_RE = re.compile(r"^\+?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def _parse_positive(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a decimal string")
    if not _DECIMAL_RE.match(value):
        raise ValueError(f"{name} is not a valid decimal string")
    try:
        d = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{name} is not a valid decimal string")
    if not d.is_finite() or d <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return d


def _scale(currency, name):
    if not isinstance(currency, str) or currency not in _SCALES:
        raise ValueError(f"unsupported {name} currency: {currency!r}")
    return _SCALES[currency]


def convert(amount: str, source: str, target: str, rate: str) -> dict:
    src_scale = _scale(source, "source")
    tgt_scale = _scale(target, "target")
    amt = _parse_positive(amount, "amount")
    r = _parse_positive(rate, "rate")

    quantum_src = Decimal(1).scaleb(-src_scale)
    quantum_tgt = Decimal(1).scaleb(-tgt_scale)
    with localcontext(Context(prec=100000, Emax=999999999, Emin=-999999999)):
        if amt % quantum_src != 0:
            raise ValueError("amount has fractional source minor units")
        product = amt * r  # exact
        result = product.quantize(quantum_tgt, rounding=ROUND_HALF_EVEN)
        minor = int(result.scaleb(tgt_scale))

    return {
        "target_minor": minor,
        "target_amount": f"{result:.{tgt_scale}f}",
        "rate": rate,
    }
