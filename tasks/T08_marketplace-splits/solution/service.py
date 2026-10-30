def allocate(gross_cents,fee_cents,weights):
    if type(gross_cents) is not int or type(fee_cents) is not int or gross_cents<=0 or fee_cents<0 or fee_cents>gross_cents or not isinstance(weights,dict) or not weights:
        raise ValueError('invalid money')
    if any(not isinstance(k,str) or not k or type(v) is not int or v<=0 for k,v in weights.items()):
        raise ValueError('invalid weights')
    net=gross_cents-fee_cents;den=sum(weights.values())
    allocated={k:(net*v)//den for k,v in weights.items()}
    remaining=net-sum(allocated.values())
    # Sort by descending raw remainder, then ascending seller ID.
    ranked=sorted(weights,key=lambda k:(-((net*weights[k])%den),k))
    for seller in ranked[:remaining]:allocated[seller]+=1
    return {'fee_cents':fee_cents,'allocations':{k:allocated[k] for k in sorted(allocated)},'payout_total_cents':net}
