def _first_occurrences(rows, source):
    first = {}
    duplicated = set()
    for row in rows:
        tid = row["transaction_id"]
        if tid in first:
            duplicated.add(tid)
        else:
            first[tid] = row
    return first, [{"source": source, "transaction_id": t} for t in sorted(duplicated)]


def reconcile(ledger: list[dict], settlement: list[dict]) -> dict:
    ledger_first, ledger_dups = _first_occurrences(ledger, "ledger")
    settle_first, settle_dups = _first_occurrences(settlement, "settlement")

    expected = {
        tid: row["gross_cents"] - row["fee_cents"]
        for tid, row in ledger_first.items()
        if row["status"] == "settled"
    }
    received = {tid: row["net_cents"] for tid, row in settle_first.items()}

    missing = sorted(tid for tid in expected if tid not in received)
    unexpected = sorted(tid for tid in received if tid not in expected)
    mismatches = [
        {"transaction_id": tid, "expected_cents": expected[tid], "received_cents": received[tid]}
        for tid in sorted(expected)
        if tid in received and received[tid] != expected[tid]
    ]

    return {
        "duplicates": ledger_dups + settle_dups,
        "missing": missing,
        "unexpected": unexpected,
        "amount_mismatches": mismatches,
        "expected_total_cents": sum(expected.values()),
        "received_total_cents": sum(received.values()),
    }
