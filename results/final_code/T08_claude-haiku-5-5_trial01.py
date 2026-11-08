def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def allocate(gross_cents, fee_cents, weights):
    if not _is_int(gross_cents) or gross_cents <= 0:
        raise ValueError("gross_cents must be a positive int")
    if not _is_int(fee_cents) or fee_cents < 0 or fee_cents > gross_cents:
        raise ValueError("fee_cents must be a nonnegative int <= gross_cents")
    if not isinstance(weights, dict) or not weights:
        raise ValueError("weights must be a nonempty dict")
    for seller, weight in weights.items():
        if not isinstance(seller, str) or not seller:
            raise ValueError("seller IDs must be nonempty strings")
        if not _is_int(weight) or weight <= 0:
            raise ValueError("weights must be positive ints")

    net = gross_cents - fee_cents
    total_weight = sum(weights.values())

    base = {}
    remainders = []
    for seller, weight in weights.items():
        product = net * weight
        base[seller] = product // total_weight
        remainders.append((product % total_weight, seller))

    leftover = net - sum(base.values())
    # Largest remainder first; ties broken by seller ID ascending.
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for i in range(leftover):
        base[remainders[i][1]] += 1

    allocations = {seller: base[seller] for seller in sorted(base)}
    return {
        "fee_cents": fee_cents,
        "allocations": allocations,
        "payout_total_cents": net,
    }
