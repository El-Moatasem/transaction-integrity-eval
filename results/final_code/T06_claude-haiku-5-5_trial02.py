import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction

# ISO 4217 currency -> minor-unit scale (number of decimal places)
_MINOR_UNIT_SCALE = {
    'USD': 2,
    'EUR': 2,
    'JPY': 0,
    'KWD': 3,
}

# Plain decimal literal: optional sign, digits with optional fraction, optional exponent.
# Rejects NaN/Infinity, underscores, whitespace, fractions like "1/2", and non-strings.
_DECIMAL_RE = re.compile(r'^\+?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$')


def _parse_positive_decimal(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a decimal string')
    if not _DECIMAL_RE.match(value):
        raise ValueError(f'{name} is not a valid decimal string: {value!r}')
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'{name} is not a valid decimal string: {value!r}') from exc
    if not d.is_finite():
        raise ValueError(f'{name} must be finite')
    if d <= 0:
        raise ValueError(f'{name} must be positive')
    return d


def _scale_for(currency, name):
    if not isinstance(currency, str) or currency not in _MINOR_UNIT_SCALE:
        raise ValueError(f'unknown {name} currency: {currency!r}')
    return _MINOR_UNIT_SCALE[currency]


def convert(amount: str, source: str, target: str, rate: str) -> dict:
    source_scale = _scale_for(source, 'source')
    target_scale = _scale_for(target, 'target')

    amount_dec = _parse_positive_decimal(amount, 'amount')
    rate_dec = _parse_positive_decimal(rate, 'rate')

    # The amount must be exactly representable in source minor units
    # (trailing zeros beyond the scale are allowed, e.g. "1.010" for USD).
    amount_exact = Fraction(amount_dec)
    if (amount_exact * (10 ** source_scale)).denominator != 1:
        raise ValueError(
            f'amount {amount!r} has fractional {source} minor units '
            f'(max {source_scale} decimal places)'
        )

    # Exact product, then a single ROUND_HALF_EVEN to the target minor-unit scale.
    scaled = amount_exact * Fraction(rate_dec) * (10 ** target_scale)
    numerator, denominator = scaled.numerator, scaled.denominator
    quotient, remainder = divmod(numerator, denominator)  # denominator > 0
    twice = 2 * remainder
    if twice > denominator or (twice == denominator and quotient % 2 == 1):
        quotient += 1
    target_minor = quotient

    if target_scale == 0:
        target_amount = str(target_minor)
    else:
        digits = str(target_minor).rjust(target_scale + 1, '0')
        target_amount = f'{digits[:-target_scale]}.{digits[-target_scale:]}'

    return {
        'target_minor': target_minor,
        'target_amount': target_amount,
        'rate': rate,
    }
