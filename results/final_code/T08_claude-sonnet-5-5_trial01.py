def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def allocate(gross_cents, fee_cents, weights):
    if not _is_int(gross_cents) or gross_cents <= 0:
        raise ValueError("gross_cents must be a positive int")
    if not _is_int(fee_cents) or fee_cents < 0 or fee_cents > gross_cents:
        raise ValueError("fee_cents must be an int in [0, gross_cents]")
    if not isinstance(weights, dict) or not weights:
        raise ValueError("weights must be a nonempty dict")
    for seller, weight in weights.items():
        if not isinstance(seller, str) or not seller:
            raise ValueError("invalid seller id")
        if not _is_int(weight) or weight <= 0:
            raise ValueError("invalid weight")

    net = gross_cents - fee_cents
    total = sum(weights.values())
    base = {}
    rem = {}
    for seller, weight in weights.items():
        q, r = divmod(net * weight, total)
        base[seller] = q
        rem[seller] = r
    leftover = net - sum(base.values())
    order = sorted(weights, key=lambda s: (-rem[s], s))
    for s in order[:leftover]:
        base[s] += 1
    allocations = {s: base[s] for s in sorted(base)}
    return {
        "fee_cents": fee_cents,
        "allocations": allocations,
        "payout_total_cents": net,
    }
