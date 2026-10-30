from datetime import datetime,timezone

def _dt(s):
    try:d=datetime.fromisoformat(s)
    except (TypeError,ValueError):raise ValueError('invalid datetime')
    if d.tzinfo is None or d.utcoffset() is None:raise ValueError('timezone required')
    return d.astimezone(timezone.utc)

def apply_dispute(dispute,event):
    try:
        if (not isinstance(event,dict) or event['dispute_id']!=dispute['dispute_id'] or not isinstance(event['event_id'],str) or not event['event_id'] or event['action'] not in ('submit_evidence','resolve_won','resolve_lost')):
            raise ValueError('invalid event')
        occurred=_dt(event['occurred_at']);deadline=_dt(dispute['evidence_deadline'])
    except (KeyError,TypeError):raise ValueError('invalid event')
    result={**dispute,'processed_ids':list(dispute['processed_ids'])}
    if event['event_id'] in dispute['processed_ids']:return result
    action=event['action'];status=dispute['status']
    if action=='submit_evidence':
        if status!='opened' or occurred>deadline:raise ValueError('invalid evidence submission')
        new_status='evidence_submitted'
    elif action in ('resolve_won','resolve_lost'):
        if status!='evidence_submitted':raise ValueError('invalid resolution')
        new_status='won' if action=='resolve_won' else 'lost'
    result['status']=new_status;result['processed_ids'].append(event['event_id']);return result
