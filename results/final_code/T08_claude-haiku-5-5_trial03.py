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

    # Hamilton / largest-remainder apportionment in pure integer arithmetic.
    floors = {}
    remainders = {}
    for seller, weight in weights.items():
        product = net * weight
        floors[seller] = product // total_weight
        remainders[seller] = product % total_weight

    leftover = net - sum(floors.values())
    # Descending remainder, ties broken by seller ID ascending.
    order = sorted(weights, key=lambda s: (-remainders[s], s))
    for seller in order[:leftover]:
        floors[seller] += 1

    allocations = {seller: floors[seller] for seller in sorted(weights)}
    return {
        "fee_cents": fee_cents,
        "allocations": allocations,
        "payout_total_cents": net,
    }
