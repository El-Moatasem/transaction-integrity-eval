import copy,pytest
from service import allocate

def test_cent_conservation_and_remainder_ties():
    assert allocate(5,0,{'b':1,'a':1})=={'fee_cents':0,'allocations':{'a':3,'b':2},'payout_total_cents':5}
    assert allocate(100,7,{'b':1,'a':2,'c':1})=={'fee_cents':7,'allocations':{'a':47,'b':23,'c':23},'payout_total_cents':93}

def test_zero_net_and_allocation_stability():
    x={'c':1,'a':1,'b':1};old=copy.deepcopy(x)
    assert allocate(1,1,x)=={'fee_cents':1,'allocations':{'a':0,'b':0,'c':0},'payout_total_cents':0}
    assert allocate(2,0,x)['allocations']=={'a':1,'b':1,'c':0}
    assert x==old

def test_nontrivial_weights():
    result=allocate(101,1,{'z':5,'a':2,'q':1})
    assert result['allocations']=={'a':25,'q':13,'z':62}
    assert sum(result['allocations'].values())==100

def test_invalid_payloads():
    for args in [(0,0,{'x':1}),(1,2,{'x':1}),(True,0,{'x':1}),(1,False,{'x':1}),(1,0,{}),(1,0,{'x':0}),(1,0,{'x':True}),(1,0,{'':1})]:
        with pytest.raises(ValueError):allocate(*args)
