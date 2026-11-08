from datetime import datetime, timezone

_ACTIONS = {
    'submit_evidence': 'evidence_submitted',
    'resolve_won': 'won',
    'resolve_lost': 'lost',
}


def _parse(ts):
    if not isinstance(ts, str):
        raise ValueError('timestamp must be a string')
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError) as e:
        raise ValueError('malformed timestamp') from e
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('naive timestamp')
    return dt.astimezone(timezone.utc)


def apply_dispute(dispute, event):
    if dispute.get('dispute_id') != event.get('dispute_id'):
        raise ValueError('dispute id mismatch')
    event_id = event.get('event_id')
    if not isinstance(event_id, str) or not event_id:
        raise ValueError('invalid event_id')
    action = event.get('action')
    if action not in _ACTIONS:
        raise ValueError('invalid action')
    occurred = _parse(event.get('occurred_at'))
    deadline = _parse(dispute.get('evidence_deadline'))

    result = dict(dispute)
    processed = list(dispute.get('processed_ids', []))
    result['processed_ids'] = processed
    if event_id in processed:
        return result

    status = dispute.get('status')
    if action == 'submit_evidence':
        if status != 'opened':
            raise ValueError('invalid transition')
        if occurred > deadline:
            raise ValueError('evidence deadline passed')
    else:
        if status != 'evidence_submitted':
            raise ValueError('invalid transition')

    processed.append(event_id)
    result['status'] = _ACTIONS[action]
    return result
