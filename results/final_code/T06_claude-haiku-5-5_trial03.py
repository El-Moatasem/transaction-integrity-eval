import re
from fractions import Fraction

# ISO-style minor-unit scales (number of decimal places) per currency.
MINOR_UNIT_SCALE = {
    "USD": 2,
    "EUR": 2,
    "JPY": 0,
    "KWD": 3,
}

# Plain positive decimal strings only: digits with an optional fractional part.
# Exponent notation, signs, whitespace, and underscores are rejected, which also
# keeps Fraction/power arithmetic bounded.
_DECIMAL_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?|\.[0-9]+|[0-9]+\.")


def _parse_positive(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a decimal string")
    if not _DECIMAL_RE.fullmatch(value):
        raise ValueError(f"{name} is not a valid decimal string: {value!r}")
    exact = Fraction(value)  # exact rational value of the decimal string
    if exact <= 0:
        raise ValueError(f"{name} must be positive")
    return exact


def _scale_for(currency, label):
    if not isinstance(currency, str) or currency not in MINOR_UNIT_SCALE:
        raise ValueError(f"unsupported {label} currency: {currency!r}")
    return MINOR_UNIT_SCALE[currency]


def convert(amount: str, source: str, target: str, rate: str) -> dict:
    source_scale = _scale_for(source, "source")
    target_scale = _scale_for(target, "target")

    amount_value = _parse_positive(amount, "amount")
    rate_value = _parse_positive(rate, "rate")

    # The amount must be exactly expressible in whole source minor units.
    if (amount_value * 10 ** source_scale).denominator != 1:
        raise ValueError("amount has fractional source minor units")

    # Exact product, then a single rounding to the target minor-unit scale.
    product = amount_value * rate_value
    target_minor = round(product * 10 ** target_scale)  # round() on Fraction: half-even

    if target_scale == 0:
        target_amount = str(target_minor)
    else:
        whole, frac = divmod(target_minor, 10 ** target_scale)
        target_amount = f"{whole}.{frac:0{target_scale}d}"

    return {
        "target_minor": target_minor,
        "target_amount": target_amount,
        "rate": rate,
    }
