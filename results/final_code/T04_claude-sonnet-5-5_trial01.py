import copy

_STATUSES = {"created", "authorized", "captured", "refunded", "cancelled"}
_EVENT_STATUSES = {"authorized", "captured", "refunded", "cancelled"}
_TRANSITIONS = {
    "created": {"authorized", "cancelled"},
    "authorized": {"captured", "cancelled"},
    "captured": {"refunded"},
    "refunded": set(),
    "cancelled": set(),
}


def _copy_state(state):
    return copy.deepcopy(state)


def apply_event(state: dict, event: dict) -> dict:
    if not isinstance(event, dict):
        raise ValueError("malformed event")
    pid = event.get("payment_id")
    eid = event.get("event_id")
    seq = event.get("sequence")
    new_status = event.get("new_status")
    if not isinstance(pid, str):
        raise ValueError("malformed payment_id")
    if not isinstance(eid, str) or not eid:
        raise ValueError("malformed event_id")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq <= 0:
        raise ValueError("malformed sequence")
    if not isinstance(new_status, str) or new_status not in _EVENT_STATUSES:
        raise ValueError("malformed new_status")
    if pid != state.get("payment_id"):
        raise ValueError("payment_id mismatch")

    if eid in state["processed_ids"] or seq <= state["last_sequence"]:
        return _copy_state(state)
    if new_status not in _TRANSITIONS.get(state["status"], set()):
        return _copy_state(state)

    result = _copy_state(state)
    result["status"] = new_status
    result["last_sequence"] = seq
    result["processed_ids"].append(eid)
    return result
