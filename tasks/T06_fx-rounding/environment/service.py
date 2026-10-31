def convert(amount,source,target,rate):
    rounded=round(float(amount)*float(rate),2)
    return {'target_minor':int(rounded*100),'target_amount':f'{rounded:.2f}','rate':rate}
