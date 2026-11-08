def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def allocate(gross_cents, fee_cents, weights):
    if not _is_int(gross_cents) or gross_cents <= 0:
        raise ValueError("gross_cents must be a positive integer")
    if not _is_int(fee_cents) or fee_cents < 0 or fee_cents > gross_cents:
        raise ValueError("fee_cents must be a nonnegative integer <= gross_cents")
    if not isinstance(weights, dict) or not weights:
        raise ValueError("weights must be a nonempty dict")

    items = list(weights.items())
    for seller, weight in items:
        if not isinstance(seller, str) or not seller:
            raise ValueError("seller IDs must be nonempty strings")
        if not _is_int(weight) or weight <= 0:
            raise ValueError("weights must be positive integers")

    net = gross_cents - fee_cents
    total = sum(w for _, w in items)

    base = {}
    remainders = []
    for seller, weight in items:
        q, r = divmod(net * weight, total)
        base[seller] = q
        remainders.append((-r, seller))

    leftover = net - sum(base.values())
    remainders.sort()
    for _, seller in remainders[:leftover]:
        base[seller] += 1

    allocations = {seller: base[seller] for seller in sorted(base)}
    if sum(allocations.values()) != net:
        raise ValueError("allocation failed to conserve cents")
    return {
        "fee_cents": fee_cents,
        "allocations": allocations,
        "payout_total_cents": net,
    }
