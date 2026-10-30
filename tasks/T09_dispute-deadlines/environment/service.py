def apply_dispute(dispute,event):
    result=dict(dispute)
    result['processed_ids']=dispute['processed_ids']+[event['event_id']]
    result['status']={'submit_evidence':'evidence_submitted','resolve_won':'won','resolve_lost':'lost'}[event['action']]
    if event['action']=='submit_evidence' and event['occurred_at']>dispute['evidence_deadline']:
        raise ValueError('late')
    return result
