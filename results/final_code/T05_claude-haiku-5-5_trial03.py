def reconcile(ledger, settlement):
    """Reconcile ledger rows against settlement rows as multisets.

    For repeated transaction IDs in either source, the first occurrence is
    authoritative; each duplicated ID is reported once per source.
    """
    duplicates = []
    ledger_first = {}
    for row in ledger:
        tid = row['transaction_id']
        if tid in ledger_first:
            duplicates.append(('ledger', tid))
        else:
            ledger_first[tid] = row

    settlement_first = {}
    for row in settlement:
        tid = row['transaction_id']
        if tid in settlement_first:
            duplicates.append(('settlement', tid))
        else:
            settlement_first[tid] = row

    # Report each duplicated ID once, sorted by source then ID.
    dup_out = [{'source': src, 'transaction_id': tid}
               for src, tid in sorted(set(duplicates))]

    settled = {tid: row for tid, row in ledger_first.items()
               if row['status'] == 'settled'}

    expected = {tid: row['gross_cents'] - row['fee_cents']
                for tid, row in settled.items()}

    missing = sorted(tid for tid in settled if tid not in settlement_first)

    unexpected = sorted(
        tid for tid in settlement_first
        if tid not in settled
    )

    mismatches = []
    for tid in sorted(settled):
        if tid in settlement_first:
            received = settlement_first[tid]['net_cents']
            if received != expected[tid]:
                mismatches.append({
                    'transaction_id': tid,
                    'expected_cents': expected[tid],
                    'received_cents': received,
                })

    return {
        'duplicates': dup_out,
        'missing': missing,
        'unexpected': unexpected,
        'amount_mismatches': mismatches,
        'expected_total_cents': sum(expected.values()),
        'received_total_cents': sum(row['net_cents']
                                    for row in settlement_first.values()),
    }
