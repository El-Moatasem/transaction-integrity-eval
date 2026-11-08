_LEGAL_TRANSITIONS = {
    "created": {"authorized", "cancelled"},
    "authorized": {"captured", "cancelled"},
    "captured": {"refunded"},
    "refunded": set(),
    "cancelled": set(),
}

_EVENT_STATUSES = {"authorized", "captured", "refunded", "cancelled"}


def _validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    for key in ("payment_id", "event_id", "sequence", "new_status"):
        if key not in event:
            raise ValueError(f"event missing key: {key}")
    if not isinstance(event["payment_id"], str):
        raise ValueError("payment_id must be a str")
    if not isinstance(event["event_id"], str) or not event["event_id"]:
        raise ValueError("event_id must be a nonempty str")
    seq = event["sequence"]
    if isinstance(seq, bool) or not isinstance(seq, int) or seq <= 0:
        raise ValueError("sequence must be a positive int")
    if event["new_status"] not in _EVENT_STATUSES:
        raise ValueError("invalid new_status")


def apply_event(state, event):
    _validate_event(event)
    if event["payment_id"] != state["payment_id"]:
        raise ValueError("payment_id mismatch")

    processed = list(state["processed_ids"])
    unchanged = {
        "payment_id": state["payment_id"],
        "status": state["status"],
        "last_sequence": state["last_sequence"],
        "processed_ids": processed,
    }

    # Duplicate or stale event: no effect.
    if event["event_id"] in processed or event["sequence"] <= state["last_sequence"]:
        return unchanged

    # Illegal transition: ignored without consuming sequence or event_id.
    if event["new_status"] not in _LEGAL_TRANSITIONS.get(state["status"], set()):
        return unchanged

    return {
        "payment_id": state["payment_id"],
        "status": event["new_status"],
        "last_sequence": event["sequence"],
        "processed_ids": processed + [event["event_id"]],
    }
