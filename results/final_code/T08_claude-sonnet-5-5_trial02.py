def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def allocate(gross_cents, fee_cents, weights):
    if not _is_int(gross_cents) or gross_cents <= 0:
        raise ValueError("gross_cents must be a positive int")
    if not _is_int(fee_cents) or fee_cents < 0 or fee_cents > gross_cents:
        raise ValueError("fee_cents must be an int in [0, gross_cents]")
    if not isinstance(weights, dict) or not weights:
        raise ValueError("weights must be a nonempty dict")
    for k, w in weights.items():
        if not isinstance(k, str) or not k:
            raise ValueError("seller ids must be nonempty strings")
        if not _is_int(w) or w <= 0:
            raise ValueError("weights must be positive ints")

    net = gross_cents - fee_cents
    total = sum(weights.values())
    base = {}
    rem = {}
    for k, w in weights.items():
        q, r = divmod(net * w, total)
        base[k] = q
        rem[k] = r
    left = net - sum(base.values())
    order = sorted(weights, key=lambda k: (-rem[k], k))
    for k in order[:left]:
        base[k] += 1
    allocations = {k: base[k] for k in sorted(base)}
    return {
        "fee_cents": fee_cents,
        "allocations": allocations,
        "payout_total_cents": net,
    }
