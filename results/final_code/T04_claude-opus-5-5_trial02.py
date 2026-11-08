STATUSES = frozenset({"created", "authorized", "captured", "refunded", "cancelled"})
EVENT_STATUSES = frozenset({"authorized", "captured", "refunded", "cancelled"})
TRANSITIONS = {
    "created": frozenset({"authorized", "cancelled"}),
    "authorized": frozenset({"captured", "cancelled"}),
    "captured": frozenset({"refunded"}),
    "refunded": frozenset(),
    "cancelled": frozenset(),
}


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_state(state):
    if not isinstance(state, dict):
        raise ValueError("state must be a dict")
    pid = state.get("payment_id")
    if not isinstance(pid, str):
        raise ValueError("state.payment_id must be a string")
    if state.get("status") not in STATUSES:
        raise ValueError("state.status is invalid")
    seq = state.get("last_sequence")
    if not _is_int(seq) or seq < 0:
        raise ValueError("state.last_sequence must be a nonnegative int")
    ids = state.get("processed_ids")
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValueError("state.processed_ids must be a list of strings")


def _validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    if not isinstance(event.get("payment_id"), str):
        raise ValueError("event.payment_id must be a string")
    eid = event.get("event_id")
    if not isinstance(eid, str) or not eid:
        raise ValueError("event.event_id must be a nonempty string")
    seq = event.get("sequence")
    if not _is_int(seq) or seq <= 0:
        raise ValueError("event.sequence must be a positive int")
    status = event.get("new_status")
    if not isinstance(status, str) or status not in EVENT_STATUSES:
        raise ValueError("event.new_status is invalid")


def _copy_state(state):
    result = dict(state)
    result["processed_ids"] = list(state["processed_ids"])
    return result


def apply_event(state: dict, event: dict) -> dict:
    _validate_state(state)
    _validate_event(event)
    if event["payment_id"] != state["payment_id"]:
        raise ValueError("payment_id mismatch")

    if event["event_id"] in state["processed_ids"]:
        return _copy_state(state)
    if event["sequence"] <= state["last_sequence"]:
        return _copy_state(state)
    if event["new_status"] not in TRANSITIONS[state["status"]]:
        # Ignore without consuming sequence or event_id so it can be retried.
        return _copy_state(state)

    result = _copy_state(state)
    result["status"] = event["new_status"]
    result["last_sequence"] = event["sequence"]
    result["processed_ids"].append(event["event_id"])
    return result
