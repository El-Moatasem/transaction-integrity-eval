from datetime import datetime, timezone

_ACTIONS = {'submit_evidence': 'evidence_submitted', 'resolve_won': 'won', 'resolve_lost': 'lost'}


def _parse(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be a string')
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        raise ValueError('malformed timestamp')
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('naive timestamp')
    return dt.astimezone(timezone.utc)


def apply_dispute(dispute, event):
    if not isinstance(dispute, dict) or not isinstance(event, dict):
        raise ValueError('invalid input')
    try:
        did, eid = event['dispute_id'], event['event_id']
        action = event['action']
        status = dispute['status']
        pids = dispute['processed_ids']
        if dispute['dispute_id'] != did:
            raise ValueError('dispute id mismatch')
        deadline = _parse(dispute['evidence_deadline'])
        occurred = _parse(event['occurred_at'])
    except KeyError as e:
        raise ValueError(f'missing field {e}')
    if not isinstance(eid, str) or not eid:
        raise ValueError('invalid event_id')
    if action not in _ACTIONS:
        raise ValueError('invalid action')
    if status not in ('opened', 'evidence_submitted', 'won', 'lost'):
        raise ValueError('invalid status')
    if not isinstance(pids, (list, tuple)):
        raise ValueError('invalid processed_ids')

    result = dict(dispute)
    result['processed_ids'] = list(pids)
    if eid in pids:
        return result

    if action == 'submit_evidence':
        if status != 'opened' or occurred > deadline:
            raise ValueError('submit_evidence not allowed')
    elif status != 'evidence_submitted':
        raise ValueError('resolution not allowed')

    result['processed_ids'].append(eid)
    result['status'] = _ACTIONS[action]
    return result
