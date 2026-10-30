import copy
from service import reconcile

def l(k,status='settled',gross=100,fee=3):return {'transaction_id':k,'status':status,'gross_cents':gross,'fee_cents':fee}
def s(k,net):return {'transaction_id':k,'net_cents':net}

def test_reconcile_all_anomalies():
    ledger=[l('a',gross=120,fee=20),l('b'),l('c','pending'),l('a',gross=200),l('d')]
    settlement=[s('a',99),s('a',100),s('c',97),s('orphan',5),s('b',97)]
    la=copy.deepcopy(ledger);sa=copy.deepcopy(settlement)
    assert reconcile(ledger,settlement)=={
      'duplicates':[{'source':'ledger','transaction_id':'a'},{'source':'settlement','transaction_id':'a'}],
      'missing':['d'],'unexpected':['c','orphan'],
      'amount_mismatches':[{'transaction_id':'a','expected_cents':100,'received_cents':99}],
      'expected_total_cents':294,'received_total_cents':298}
    assert ledger==la and settlement==sa

def test_duplicate_first_occurrence_is_authoritative():
    r=reconcile([l('x',gross=1000,fee=10),l('x',gross=2000,fee=50)],[s('x',990),s('x',3000)])
    assert r['duplicates']==[{'source':'ledger','transaction_id':'x'},{'source':'settlement','transaction_id':'x'}]
    assert r['amount_mismatches']==[]
    assert r['expected_total_cents']==990 and r['received_total_cents']==990

def test_empty_and_all_pending():
    assert reconcile([],[])=={'duplicates':[],'missing':[],'unexpected':[],'amount_mismatches':[],'expected_total_cents':0,'received_total_cents':0}
    r=reconcile([l('p','pending')],[s('p',97)])
    assert r['unexpected']==['p'] and r['missing']==[] and r['expected_total_cents']==0 and r['received_total_cents']==97
