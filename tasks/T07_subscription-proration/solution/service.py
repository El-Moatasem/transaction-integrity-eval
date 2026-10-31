from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_EVEN

def _parse(value):
    try:d=datetime.fromisoformat(value)
    except (TypeError,ValueError):raise ValueError('invalid datetime')
    if d.tzinfo is None or d.utcoffset() is None or d.microsecond!=0:raise ValueError('timezone and second precision required')
    return d.astimezone(timezone.utc)

def prorate(period_start,period_end,effective_at,old_cents,new_cents):
    if type(old_cents) is not int or type(new_cents) is not int or min(old_cents,new_cents)<0:raise ValueError('invalid rate')
    start=_parse(period_start);end=_parse(period_end);at=_parse(effective_at)
    if not start<end or not start<=at<=end:raise ValueError('invalid period')
    total=int((end-start).total_seconds());rem=int((end-at).total_seconds());elapsed=total-rem
    charge=(Decimal(old_cents)*Decimal(elapsed)/Decimal(total)+Decimal(new_cents)*Decimal(rem)/Decimal(total)).quantize(Decimal('1'),rounding=ROUND_HALF_EVEN)
    return {'charge_cents':int(charge),'total_seconds':total,'remaining_seconds':rem}
