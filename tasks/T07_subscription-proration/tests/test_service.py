import pytest
from service import prorate

A='2026-03-28T12:00:00+00:00';B='2026-03-30T12:00:00+00:00'

def test_exact_hours_not_calendar_days():
    r=prorate(A,B,'2026-03-29T00:00:00+00:00',100,200)
    assert r=={'charge_cents':175,'total_seconds':172800,'remaining_seconds':129600}

def test_offset_instants_and_boundaries():
    r=prorate(A,B,'2026-03-29T02:00:00+02:00',100,200)
    assert r['charge_cents']==175
    assert prorate(A,B,A,100,300)['charge_cents']==300
    assert prorate(A,B,B,100,300)['charge_cents']==100

def test_half_even_round_total_once():
    r=prorate('2026-01-01T00:00:00Z','2026-01-01T00:00:02Z','2026-01-01T00:00:01Z',0,1)
    assert r=={'charge_cents':0,'total_seconds':2,'remaining_seconds':1}
    r2=prorate('2026-01-01T00:00:00Z','2026-01-01T00:00:04Z','2026-01-01T00:00:01Z',1,2)
    assert r2['charge_cents']==2

def test_invalid_period():
    for a,b,e,old,new in [(A,A,A,1,2),(A,B,'2026-04-01T00:00:00Z',1,2),('2026-03-28T12:00:00',B,A,1,2),(A,B,A,True,2),(A,B,A,-1,2),(A,B,'2026-03-29T00:00:00.500Z',1,2)]:
        with pytest.raises(ValueError):prorate(a,b,e,old,new)
