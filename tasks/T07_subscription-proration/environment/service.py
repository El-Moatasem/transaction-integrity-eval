from datetime import datetime

def prorate(period_start,period_end,effective_at,old_cents,new_cents):
    a=datetime.fromisoformat(period_start);b=datetime.fromisoformat(period_end);e=datetime.fromisoformat(effective_at)
    days=(b.date()-a.date()).days
    remaining=(b.date()-e.date()).days
    charge=round(old_cents*(days-remaining)/days+new_cents*remaining/days)
    return {'charge_cents':charge,'total_seconds':days*86400,'remaining_seconds':remaining*86400}
