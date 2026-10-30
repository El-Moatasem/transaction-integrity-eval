from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
SCALES={'USD':2,'EUR':2,'JPY':0,'KWD':3}
def convert(amount,source,target,rate):
    if not isinstance(amount,str) or not isinstance(rate,str) or source not in SCALES or target not in SCALES:raise ValueError()
    try:a=Decimal(amount);r=Decimal(rate)
    except InvalidOperation:raise ValueError()
    if not a.is_finite() or not r.is_finite() or a<=0 or r<=0 or a*10**SCALES[source]!=(a*10**SCALES[source]).to_integral_value():raise ValueError()
    scale=SCALES[target];d=(a*r).quantize(Decimal(1).scaleb(-scale),rounding=ROUND_HALF_UP)
    return {'target_minor':int(d*10**scale),'target_amount':f'{d:.{scale}f}','rate':rate}
