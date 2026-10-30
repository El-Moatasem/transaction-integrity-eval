def reconcile(ledger,settlement):
    l={x['transaction_id']:x for x in ledger}
    s={x['transaction_id']:x for x in settlement}
    return {'duplicates':[],'missing':[],'unexpected':[], 'amount_mismatches':[],
            'expected_total_cents':sum(v['gross_cents']-v['fee_cents'] for v in l.values() if v['status']=='settled'),
            'received_total_cents':sum(v['net_cents'] for v in s.values())}
