TRANSITIONS={'created':{'authorized','cancelled'},'authorized':{'captured','cancelled'},'captured':{'refunded'},'refunded':set(),'cancelled':set()}

def apply_event(state,event):
    try:
        if (not isinstance(event,dict) or event['payment_id']!=state['payment_id'] or not isinstance(event['event_id'],str) or not event['event_id'] or type(event['sequence']) is not int or event['sequence']<=0 or event['new_status'] not in {'authorized','captured','refunded','cancelled'} or state['status'] not in TRANSITIONS or type(state['last_sequence']) is not int or not isinstance(state['processed_ids'],list)):
            raise ValueError('invalid event')
    except (KeyError,TypeError):raise ValueError('invalid event')
    result=dict(state)
    result['processed_ids']=list(state['processed_ids'])
    if event['event_id'] in state['processed_ids'] or event['sequence']<=state['last_sequence']:
        return result
    if event['new_status'] not in TRANSITIONS[state['status']]:return result
    result['status']=event['new_status'];result['last_sequence']=event['sequence'];result['processed_ids'].append(event['event_id'])
    return result
