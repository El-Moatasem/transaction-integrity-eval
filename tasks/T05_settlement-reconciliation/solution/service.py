def reconcile(ledger,settlement):
    left={};right={};dup=set()
    for row in ledger:
        key=row['transaction_id']
        if key in left:dup.add(('ledger',key))
        else:left[key]=row
    for row in settlement:
        key=row['transaction_id']
        if key in right:dup.add(('settlement',key))
        else:right[key]=row
    settled={k:v for k,v in left.items() if v['status']=='settled'}
    missing=sorted(set(settled)-set(right))
    unexpected=sorted(set(right)-set(settled))
    mismatches=[]
    for key in sorted(set(settled)&set(right)):
        expected=settled[key]['gross_cents']-settled[key]['fee_cents'];received=right[key]['net_cents']
        if expected!=received:mismatches.append({'transaction_id':key,'expected_cents':expected,'received_cents':received})
    return {'duplicates':[{'source':source,'transaction_id':key} for source,key in sorted(dup)],
            'missing':missing,'unexpected':unexpected,'amount_mismatches':mismatches,
            'expected_total_cents':sum(v['gross_cents']-v['fee_cents'] for v in settled.values()),
            'received_total_cents':sum(v['net_cents'] for v in right.values())}
