_TRANSITIONS = {
    'created': {'authorized', 'cancelled'},
    'authorized': {'captured', 'cancelled'},
    'captured': {'refunded'},
    'refunded': set(),
    'cancelled': set(),
}
_TARGETS = {'authorized', 'captured', 'refunded', 'cancelled'}


def _copy(state):
    result = dict(state)
    result['processed_ids'] = list(state['processed_ids'])
    return result


def apply_event(state, event):
    if not isinstance(event, dict):
        raise ValueError('malformed event')
    for k in ('payment_id', 'event_id', 'sequence', 'new_status'):
        if k not in event:
            raise ValueError('malformed event')
    eid = event['event_id']
    seq = event['sequence']
    new = event['new_status']
    if not isinstance(event['payment_id'], str):
        raise ValueError('bad payment_id')
    if not isinstance(eid, str) or not eid:
        raise ValueError('bad event_id')
    if isinstance(seq, bool) or not isinstance(seq, int) or seq <= 0:
        raise ValueError('bad sequence')
    if not isinstance(new, str) or new not in _TARGETS:
        raise ValueError('bad new_status')
    if event['payment_id'] != state['payment_id']:
        raise ValueError('payment_id mismatch')

    if eid in state['processed_ids'] or seq <= state['last_sequence']:
        return _copy(state)
    if new not in _TRANSITIONS.get(state['status'], set()):
        return _copy(state)

    result = _copy(state)
    result['status'] = new
    result['last_sequence'] = seq
    result['processed_ids'].append(eid)
    return result
