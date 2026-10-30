TRANSITIONS={'created':{'authorized','cancelled'},'authorized':{'captured','cancelled'},'captured':{'refunded'},'refunded':set(),'cancelled':set()}
def apply_event(state,event):
    if event['payment_id']!=state['payment_id'] or type(event['sequence']) is not int or event['sequence']<=0 or not event['event_id'] or event['new_status'] not in {'authorized','captured','refunded','cancelled'}:raise ValueError()
    r={**state,'processed_ids':list(state['processed_ids'])}
    if event['event_id'] in state['processed_ids'] or event['sequence']<state['last_sequence']:return r
    if event['new_status'] not in TRANSITIONS[state['status']]:return r
    r['status']=event['new_status'];r['last_sequence']=event['sequence'];r['processed_ids'].append(event['event_id']);return r
