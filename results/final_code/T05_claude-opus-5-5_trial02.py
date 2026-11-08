def _first_occurrences(rows):
    """Return (dict of first occurrence by ID, set of duplicated IDs)."""
    first = {}
    dups = set()
    for row in rows:
        tid = row["transaction_id"]
        if tid in first:
            dups.add(tid)
        else:
            first[tid] = row
    return first, dups


def reconcile(ledger: list[dict], settlement: list[dict]) -> dict:
    ledger_by_id, ledger_dups = _first_occurrences(ledger)
    settle_by_id, settle_dups = _first_occurrences(settlement)

    duplicates = [{"source": "ledger", "transaction_id": t} for t in sorted(ledger_dups)]
    duplicates += [{"source": "settlement", "transaction_id": t} for t in sorted(settle_dups)]

    expected = {
        tid: row["gross_cents"] - row["fee_cents"]
        for tid, row in ledger_by_id.items()
        if row["status"] == "settled"
    }

    missing = sorted(tid for tid in expected if tid not in settle_by_id)
    unexpected = sorted(tid for tid in settle_by_id if tid not in expected)

    mismatches = []
    for tid in sorted(expected):
        if tid in settle_by_id:
            received = settle_by_id[tid]["net_cents"]
            if received != expected[tid]:
                mismatches.append(
                    {"transaction_id": tid, "expected_cents": expected[tid], "received_cents": received}
                )

    return {
        "duplicates": duplicates,
        "missing": missing,
        "unexpected": unexpected,
        "amount_mismatches": mismatches,
        "expected_total_cents": sum(expected.values()),
        "received_total_cents": sum(r["net_cents"] for r in settle_by_id.values()),
    }
