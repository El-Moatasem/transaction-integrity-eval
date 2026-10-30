from datetime import datetime,timezone
def dt(s):
    d=datetime.fromisoformat(s)
    if d.tzinfo is None:raise ValueError()
    return d.astimezone(timezone.utc)
def apply_dispute(dispute,event):
    if event['dispute_id']!=dispute['dispute_id'] or not event['event_id'] or event['action'] not in ('submit_evidence','resolve_won','resolve_lost'):raise ValueError()
    occurred=dt(event['occurred_at']);deadline=dt(dispute['evidence_deadline'])
    r={**dispute,'processed_ids':list(dispute['processed_ids'])}
    if event['event_id'] in dispute['processed_ids']:return r
    if event['action']=='submit_evidence':
        if dispute['status']!='opened' or occurred>=deadline:raise ValueError('wrongly exclusive deadline')
        r['status']='evidence_submitted'
    else:
        if dispute['status']!='evidence_submitted':raise ValueError()
        r['status']='won' if event['action']=='resolve_won' else 'lost'
    r['processed_ids'].append(event['event_id']);return r
