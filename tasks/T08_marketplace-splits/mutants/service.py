def allocate(gross_cents,fee_cents,weights):
    if type(gross_cents) is not int or type(fee_cents) is not int or gross_cents<=0 or fee_cents<0 or fee_cents>gross_cents or not isinstance(weights,dict) or not weights:raise ValueError()
    if any(not isinstance(k,str) or not k or type(v) is not int or v<=0 for k,v in weights.items()):raise ValueError()
    net=gross_cents-fee_cents;den=sum(weights.values())
    a={k:(net*v)//den for k,v in weights.items()}
    left=net-sum(a.values())
    # WRONG: tie-breaks in reverse lexical order.
    rank=sorted(weights,key=lambda k:k,reverse=True)
    rank=sorted(rank,key=lambda k:(net*weights[k])%den,reverse=True)
    for k in rank[:left]:a[k]+=1
    return {'fee_cents':fee_cents,'allocations':{k:a[k] for k in sorted(a)},'payout_total_cents':net}
