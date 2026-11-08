def reconcile(ledger, settlement):
    l = {}
    s = {}
    dups = set()
    for x in ledger:
        i = x['transaction_id']
        if i in l:
            dups.add(('ledger', i))
        else:
            l[i] = x
    for x in settlement:
        i = x['transaction_id']
        if i in s:
            dups.add(('settlement', i))
        else:
            s[i] = x

    expected = {i: v['gross_cents'] - v['fee_cents']
                for i, v in l.items() if v['status'] == 'settled'}
    missing = sorted(i for i in expected if i not in s)
    unexpected = sorted(i for i in s if i not in expected)
    mismatches = [
        {'transaction_id': i, 'expected_cents': expected[i],
         'received_cents': s[i]['net_cents']}
        for i in sorted(expected)
        if i in s and s[i]['net_cents'] != expected[i]
    ]
    return {
        'duplicates': [{'source': src, 'transaction_id': i} for src, i in sorted(dups)],
        'missing': missing,
        'unexpected': unexpected,
        'amount_mismatches': mismatches,
        'expected_total_cents': sum(expected.values()),
        'received_total_cents': sum(v['net_cents'] for v in s.values()),
    }
