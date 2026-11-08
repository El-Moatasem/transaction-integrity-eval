def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def allocate(gross_cents: int, fee_cents: int, weights: dict) -> dict:
    """Split net proceeds among sellers using Hamilton (largest-remainder)
    apportionment, in integer arithmetic only.

    Each seller first receives floor(net * w / W). The leftover cents are then
    handed out one at a time in descending order of the integer remainder
    (net * w) % W, with ties broken by seller ID in ascending lexical order.
    """
    if not _is_int(gross_cents) or gross_cents <= 0:
        raise ValueError("gross_cents must be a positive int")
    if not _is_int(fee_cents) or fee_cents < 0 or fee_cents > gross_cents:
        raise ValueError("fee_cents must be an int with 0 <= fee_cents <= gross_cents")
    if not isinstance(weights, dict) or not weights:
        raise ValueError("weights must be a nonempty dict")
    for seller_id, weight in weights.items():
        if not isinstance(seller_id, str) or not seller_id:
            raise ValueError("seller IDs must be nonempty strings")
        if not _is_int(weight) or weight <= 0:
            raise ValueError("weights must be positive ints")

    net = gross_cents - fee_cents
    total_weight = sum(weights.values())

    floors = {}
    remainders = {}
    for seller_id, weight in weights.items():
        product = net * weight
        floors[seller_id] = product // total_weight
        remainders[seller_id] = product % total_weight

    leftover = net - sum(floors.values())
    # Ranking: largest remainder first, ties by seller ID ascending.
    ranked = sorted(weights, key=lambda s: (-remainders[s], s))
    for i in range(leftover):
        floors[ranked[i]] += 1

    allocations = {seller_id: floors[seller_id] for seller_id in sorted(weights)}
    return {
        "fee_cents": fee_cents,
        "allocations": allocations,
        "payout_total_cents": net,
    }
