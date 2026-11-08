def reconcile(ledger: list[dict], settlement: list[dict]) -> dict:
    # First occurrence of each ID is authoritative; later repeats are only reported.
    led: dict[str, dict] = {}
    led_dups: set[str] = set()
    for row in ledger:
        tid = row["transaction_id"]
        if tid in led:
            led_dups.add(tid)
        else:
            led[tid] = row

    stl: dict[str, dict] = {}
    stl_dups: set[str] = set()
    for row in settlement:
        tid = row["transaction_id"]
        if tid in stl:
            stl_dups.add(tid)
        else:
            stl[tid] = row

    duplicates = [{"source": "ledger", "transaction_id": tid} for tid in sorted(led_dups)]
    duplicates += [{"source": "settlement", "transaction_id": tid} for tid in sorted(stl_dups)]

    settled = {tid: row for tid, row in led.items() if row["status"] == "settled"}
    expected = {tid: row["gross_cents"] - row["fee_cents"] for tid, row in settled.items()}

    missing = sorted(tid for tid in settled if tid not in stl)

    unexpected = sorted(
        tid for tid in stl if tid not in settled
    )

    amount_mismatches = []
    for tid in sorted(settled):
        if tid in stl and stl[tid]["net_cents"] != expected[tid]:
            amount_mismatches.append({
                "transaction_id": tid,
                "expected_cents": expected[tid],
                "received_cents": stl[tid]["net_cents"],
            })

    return {
        "duplicates": duplicates,
        "missing": missing,
        "unexpected": unexpected,
        "amount_mismatches": amount_mismatches,
        "expected_total_cents": sum(expected.values()),
        "received_total_cents": sum(row["net_cents"] for row in stl.values()),
    }
