def reconcile(ledger, settlement):
    # First occurrence is authoritative for each source.
    first_l = {}
    first_s = {}
    dup_l = set()
    dup_s = set()
    for row in ledger:
        tid = row['transaction_id']
        if tid in first_l:
            dup_l.add(tid)
        else:
            first_l[tid] = row
    for row in settlement:
        tid = row['transaction_id']
        if tid in first_s:
            dup_s.add(tid)
        else:
            first_s[tid] = row

    duplicates = (
        [{'source': 'ledger', 'transaction_id': t} for t in sorted(dup_l)]
        + [{'source': 'settlement', 'transaction_id': t} for t in sorted(dup_s)]
    )

    settled = {t: r for t, r in first_l.items() if r['status'] == 'settled'}
    expected = {t: r['gross_cents'] - r['fee_cents'] for t, r in settled.items()}

    missing = sorted(t for t in settled if t not in first_s)

    unexpected = sorted(
        t for t in first_s
        if t not in first_l or first_l[t]['status'] == 'pending'
    )

    amount_mismatches = []
    for t in sorted(settled):
        if t in first_s:
            received = first_s[t]['net_cents']
            if received != expected[t]:
                amount_mismatches.append({
                    'transaction_id': t,
                    'expected_cents': expected[t],
                    'received_cents': received,
                })

    return {
        'duplicates': duplicates,
        'missing': missing,
        'unexpected': unexpected,
        'amount_mismatches': amount_mismatches,
        'expected_total_cents': sum(expected.values()),
        'received_total_cents': sum(r['net_cents'] for r in first_s.values()),
    }
