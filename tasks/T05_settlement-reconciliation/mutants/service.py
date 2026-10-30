def reconcile(ledger,settlement):
    left={};right={};dup=set()
    for x in ledger:
        if x['transaction_id'] in left:dup.add(('ledger',x['transaction_id']))
        else:left[x['transaction_id']]=x
    for x in settlement:
        if x['transaction_id'] in right:dup.add(('settlement',x['transaction_id']))
        else:right[x['transaction_id']]=x
    settled={k:v for k,v in left.items() if v['status']=='settled'}
    missing=sorted(set(settled)-set(right));unexpected=sorted(set(right)-set(settled))
    mismatch=[]
    for k in sorted(set(settled)&set(right)):
        ex=settled[k]['gross_cents']-settled[k]['fee_cents']
        # Deliberately tolerates off-by-one settlement errors.
        if abs(ex-right[k]['net_cents'])>1:mismatch.append({'transaction_id':k,'expected_cents':ex,'received_cents':right[k]['net_cents']})
    return {'duplicates':[{'source':a,'transaction_id':b} for a,b in sorted(dup)],'missing':missing,
            'unexpected':unexpected,'amount_mismatches':mismatch,
            'expected_total_cents':sum(v['gross_cents']-v['fee_cents'] for v in settled.values()),
            'received_total_cents':sum(v['net_cents'] for v in right.values())}
