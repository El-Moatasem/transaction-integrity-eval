import pytest,copy
from service import apply_dispute

def state():return {'dispute_id':'d1','status':'opened','evidence_deadline':'2026-06-30T20:00:00+00:00','processed_ids':[]}
def ev(k,action,t='2026-06-30T22:00:00+02:00',d='d1'):return {'dispute_id':d,'event_id':k,'action':action,'occurred_at':t}

def test_inclusive_timezone_boundary():
    d=state();e=ev('x','submit_evidence')
    result=apply_dispute(d,e)
    assert result=={'dispute_id':'d1','status':'evidence_submitted','evidence_deadline':d['evidence_deadline'],'processed_ids':['x']}
    assert d['processed_ids']==[] and d['status']=='opened'
    assert apply_dispute(result,e)==result
    assert apply_dispute(result,ev('resolve','resolve_won','2026-07-08T00:00:00Z'))['status']=='won'

def test_late_and_invalid_transitions():
    d=state()
    for e in [ev('late','submit_evidence','2026-06-30T20:00:01Z'),ev('premature','resolve_lost'),ev('wrong','submit_evidence',d='other'),ev('naive','submit_evidence','2026-06-30T19:00:00')]:
        with pytest.raises(ValueError):apply_dispute(d,e)
    assert d==state()

def test_terminal_states_and_exactly_once():
    d=apply_dispute(state(),ev('e','submit_evidence'))
    d=apply_dispute(d,ev('win','resolve_won','2026-08-01T00:00:00Z'))
    assert apply_dispute(d,ev('win','resolve_won','2026-08-01T00:00:00Z'))==d
    for action in ['resolve_lost','submit_evidence']:
        with pytest.raises(ValueError):apply_dispute(d,ev('new',action))
