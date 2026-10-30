def apply_event(state,event):
    result=dict(state)
    result['status']=event['new_status']
    result['last_sequence']=max(state['last_sequence'],event['sequence'])
    result['processed_ids']=list(state['processed_ids'])+[event['event_id']]
    return result
