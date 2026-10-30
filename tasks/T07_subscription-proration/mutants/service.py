from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
def _parse(x):
    d=datetime.fromisoformat(x)
    if d.tzinfo is None or d.microsecond:raise ValueError()
    return d.astimezone(timezone.utc)
def prorate(period_start,period_end,effective_at,old_cents,new_cents):
    if type(old_cents) is not int or type(new_cents) is not int or min(old_cents,new_cents)<0:raise ValueError()
    s=_parse(period_start);e=_parse(period_end);t=_parse(effective_at)
    if not s<e or not s<=t<=e:raise ValueError()
    total=int((e-s).total_seconds());rem=int((e-t).total_seconds())
    charge=(Decimal(old_cents)*(total-rem)/total+Decimal(new_cents)*rem/total).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
    return {'charge_cents':int(charge),'total_seconds':total,'remaining_seconds':rem}
