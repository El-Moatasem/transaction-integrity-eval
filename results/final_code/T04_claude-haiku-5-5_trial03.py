_STATUSES = frozenset({"created", "authorized", "captured", "refunded", "cancelled"})
_EVENT_STATUSES = frozenset({"authorized", "captured", "refunded", "cancelled"})
_TRANSITIONS = {
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
    if not isinstance(state.get("payment_id"), str):
        raise ValueError("state.payment_id must be a str")
    if state.get("status") not in _STATUSES:
        raise ValueError("state.status is invalid")
    last_sequence = state.get("last_sequence")
    if not _is_int(last_sequence) or last_sequence < 0:
        raise ValueError("state.last_sequence must be a nonnegative int")
    processed_ids = state.get("processed_ids")
    if not isinstance(processed_ids, list) or not all(isinstance(i, str) for i in processed_ids):
        raise ValueError("state.processed_ids must be a list of str")


def _validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    if not isinstance(event.get("payment_id"), str):
        raise ValueError("event.payment_id must be a str")
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event.event_id must be a nonempty str")
    sequence = event.get("sequence")
    if not _is_int(sequence) or sequence <= 0:
        raise ValueError("event.sequence must be a positive int")
    if event.get("new_status") not in _EVENT_STATUSES:
        raise ValueError("event.new_status is invalid")


def _copy_state(state):
    return {
        "payment_id": state["payment_id"],
        "status": state["status"],
        "last_sequence": state["last_sequence"],
        "processed_ids": list(state["processed_ids"]),
    }


def apply_event(state: dict, event: dict) -> dict:
    _validate_state(state)
    _validate_event(event)

    if event["payment_id"] != state["payment_id"]:
        raise ValueError("payment_id mismatch")

    # Duplicate or stale events leave state unchanged.
    if event["event_id"] in state["processed_ids"]:
        return _copy_state(state)
    if event["sequence"] <= state["last_sequence"]:
        return _copy_state(state)

    # Illegal transitions are ignored without consuming sequence or event_id,
    # so the event may be retried once earlier events have arrived.
    if event["new_status"] not in _TRANSITIONS[state["status"]]:
        return _copy_state(state)

    result = _copy_state(state)
    result["status"] = event["new_status"]
    result["last_sequence"] = event["sequence"]
    result["processed_ids"].append(event["event_id"])
    return result
