from datetime import datetime, timezone

_ACTIONS = {
    'submit_evidence': 'evidence_submitted',
    'resolve_won': 'won',
    'resolve_lost': 'lost',
}
_STATUSES = {'opened', 'evidence_submitted', 'won', 'lost'}


def _parse(ts):
    if not isinstance(ts, str):
        raise ValueError('malformed timestamp')
    try:
        dt = datetime.fromisoformat(ts.strip())
    except (ValueError, TypeError):
        raise ValueError('malformed timestamp')
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError('naive timestamp')
    return dt.astimezone(timezone.utc)


def apply_dispute(dispute, event):
    if not isinstance(dispute, dict) or not isinstance(event, dict):
        raise ValueError('invalid input')
    try:
        did = dispute['dispute_id']
        status = dispute['status']
        processed = dispute['processed_ids']
        deadline_raw = dispute['evidence_deadline']
        eid = event['event_id']
        action = event['action']
        occurred_raw = event['occurred_at']
        event_did = event['dispute_id']
    except KeyError as e:
        raise ValueError('missing field %s' % e)
    if event_did != did:
        raise ValueError('dispute id mismatch')
    if not isinstance(eid, str) or not eid:
        raise ValueError('invalid event_id')
    if action not in _ACTIONS:
        raise ValueError('invalid action')
    if status not in _STATUSES:
        raise ValueError('invalid status')
    if not isinstance(processed, (list, tuple)):
        raise ValueError('invalid processed_ids')
    occurred = _parse(occurred_raw)
    deadline = _parse(deadline_raw)

    result = dict(dispute)
    if eid in processed:
        result['processed_ids'] = list(processed)
        return result

    if action == 'submit_evidence':
        if status != 'opened':
            raise ValueError('invalid transition')
        if occurred > deadline:
            raise ValueError('evidence deadline passed')
    else:
        if status != 'evidence_submitted':
            raise ValueError('invalid transition')

    result['processed_ids'] = list(processed) + [eid]
    result['status'] = _ACTIONS[action]
    return result
