STATUSES = {"created", "authorized", "captured", "refunded", "cancelled"}
EVENT_STATUSES = {"authorized", "captured", "refunded", "cancelled"}
TRANSITIONS = {
    ("created", "authorized"),
    ("created", "cancelled"),
    ("authorized", "captured"),
    ("authorized", "cancelled"),
    ("captured", "refunded"),
}


def _copy(state):
    result = dict(state)
    result["processed_ids"] = list(state["processed_ids"])
    return result


def apply_event(state, event):
    if not isinstance(event, dict):
        raise ValueError("malformed event")
    pid = event.get("payment_id")
    eid = event.get("event_id")
    seq = event.get("sequence")
    new = event.get("new_status")
    if not isinstance(pid, str):
        raise ValueError("malformed payment_id")
    if not isinstance(eid, str) or not eid:
        raise ValueError("malformed event_id")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq <= 0:
        raise ValueError("malformed sequence")
    if not isinstance(new, str) or new not in EVENT_STATUSES:
        raise ValueError("malformed new_status")
    if pid != state.get("payment_id"):
        raise ValueError("payment_id mismatch")

    if eid in state["processed_ids"] or seq <= state["last_sequence"]:
        return _copy(state)
    if (state["status"], new) not in TRANSITIONS:
        return _copy(state)

    result = _copy(state)
    result["status"] = new
    result["last_sequence"] = seq
    result["processed_ids"].append(eid)
    return result
