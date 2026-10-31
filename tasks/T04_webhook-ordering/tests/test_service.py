import copy,pytest
from service import apply_event

def initial():return {'payment_id':'p1','status':'created','last_sequence':0,'processed_ids':[]}
def ev(eid,seq,status,pid='p1'):return {'payment_id':pid,'event_id':eid,'sequence':seq,'new_status':status}

def test_out_of_order_and_recovery():
    s=initial();future=ev('capture',3,'captured');old=copy.deepcopy(s)
    assert apply_event(s,future)==old and s==old
    a=apply_event(s,ev('auth',2,'authorized'))
    b=apply_event(a,future)
    assert b=={'payment_id':'p1','status':'captured','last_sequence':3,'processed_ids':['auth','capture']}
    assert a['status']=='authorized' and s['processed_ids']==[]
    assert apply_event(b,ev('refund',4,'refunded'))['status']=='refunded'

def test_stale_duplicate_and_terminal():
    s=apply_event(initial(),ev('a',1,'authorized'))
    assert apply_event(s,ev('a',50,'captured'))==s
    assert apply_event(s,ev('different',1,'captured'))==s
    finished=apply_event(s,ev('cancel',2,'cancelled'))
    assert apply_event(finished,ev('later',8,'captured'))==finished
    assert finished['last_sequence']==2

def test_unrelated_or_invalid_events():
    s=initial()
    for e in [ev('bad',1,'authorized','other'),ev('',1,'authorized'),ev('a',True,'authorized'),ev('a',0,'authorized'),ev('a',1,'unknown')]:
        with pytest.raises(ValueError):apply_event(s,e)
    assert s==initial()
