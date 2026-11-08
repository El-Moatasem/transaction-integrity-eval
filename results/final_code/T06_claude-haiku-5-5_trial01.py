import re
from fractions import Fraction

# ISO-style currency -> minor-unit scale (number of decimal places).
_MINOR_SCALE = {'USD': 2, 'EUR': 2, 'JPY': 0, 'KWD': 3}

# Plain decimal string: digits with optional fraction and optional exponent.
# No signs, whitespace, underscores, or non-finite spellings are accepted here.
_DECIMAL_RE = re.compile(r'(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][+-]?\d+)?', re.ASCII)


def _parse_decimal(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a decimal string')
    if not _DECIMAL_RE.fullmatch(value):
        raise ValueError(f'{name} is not a valid decimal string: {value!r}')
    parsed = Fraction(value)  # exact rational value of the decimal string
    if parsed <= 0:
        raise ValueError(f'{name} must be positive')
    return parsed


def _currency_scale(code, name):
    if not isinstance(code, str) or code not in _MINOR_SCALE:
        raise ValueError(f'unsupported {name} currency: {code!r}')
    return _MINOR_SCALE[code]


def convert(amount: str, source: str, target: str, rate: str) -> dict:
    source_scale = _currency_scale(source, 'source')
    target_scale = _currency_scale(target, 'target')

    amount_value = _parse_decimal(amount, 'amount')
    rate_value = _parse_decimal(rate, 'rate')

    # The amount must be exactly expressible in whole source minor units.
    source_minor_exact = amount_value * (10 ** source_scale)
    if source_minor_exact.denominator != 1:
        raise ValueError(
            f'amount has fractional {source} minor units: {amount!r}'
        )

    # Exact product, then a single round-half-even to target minor units.
    # Fraction.__round__ with no ndigits uses round-half-even.
    target_minor = round(amount_value * rate_value * (10 ** target_scale))

    if target_scale == 0:
        target_amount = str(target_minor)
    else:
        unit = 10 ** target_scale
        whole, frac = divmod(target_minor, unit)
        target_amount = f'{whole}.{frac:0{target_scale}d}'

    return {
        'target_minor': int(target_minor),
        'target_amount': target_amount,
        'rate': rate,
    }
