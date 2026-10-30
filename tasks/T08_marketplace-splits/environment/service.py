def allocate(gross_cents,fee_cents,weights):
    net=gross_cents-fee_cents
    total=sum(weights.values())
    result={seller:round(net*weight/total) for seller,weight in weights.items()}
    return {'fee_cents':fee_cents,'allocations':result,'payout_total_cents':net}
