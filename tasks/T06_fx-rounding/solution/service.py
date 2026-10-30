from decimal import Decimal,InvalidOperation,ROUND_HALF_EVEN
SCALES={'USD':2,'EUR':2,'JPY':0,'KWD':3}

def convert(amount,source,target,rate):
    if not isinstance(amount,str) or not isinstance(rate,str) or source not in SCALES or target not in SCALES:
        raise ValueError('invalid input')
    try:
        a=Decimal(amount);r=Decimal(rate)
    except InvalidOperation:raise ValueError('invalid decimal')
    if not a.is_finite() or not r.is_finite() or a<=0 or r<=0:raise ValueError('invalid value')
    src_factor=10**SCALES[source]
    if a*src_factor != (a*src_factor).to_integral_value():raise ValueError('fractional source minor unit')
    scale=SCALES[target];factor=10**scale
    quantum=Decimal(1).scaleb(-scale)
    target_amount=(a*r).quantize(quantum,rounding=ROUND_HALF_EVEN)
    return {'target_minor':int(target_amount*factor),'target_amount':f'{target_amount:.{scale}f}','rate':rate}
