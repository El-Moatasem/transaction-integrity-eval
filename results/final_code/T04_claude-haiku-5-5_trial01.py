_STATUSES = frozenset({"created", "authorized", "captured", "refunded", "cancelled"})
_EVENT_STATUSES = frozenset({"authorized", "captured", "refunded", "cancelled"})

# Legal transitions. refunded and cancelled are terminal (no outgoing edges).
_TRANSITIONS = {
    "created": frozenset({"authorized", "cancelled"}),
    "authorized": frozenset({"captured", "cancelled"}),
    "captured": frozenset({"refunded"}),
    "refunded": frozenset(),
    "cancelled": frozenset(),
}


def _copy_state(state):
    return {
        "payment_id": state["payment_id"],
        "status": state["status"],
        "last_sequence": state["last_sequence"],
        "processed_ids": list(state["processed_ids"]),
    }


def _validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    payment_id = event.get("payment_id")
    if not isinstance(payment_id, str):
        raise ValueError("event payment_id must be a str")
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a nonempty str")
    sequence = event.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        raise ValueError("sequence must be a positive int")
    new_status = event.get("new_status")
    if new_status not in _EVENT_STATUSES:
        raise ValueError("invalid new_status")


def apply_event(state: dict, event: dict) -> dict:
    _validate_event(event)
    if event["payment_id"] != state["payment_id"]:
        raise ValueError("payment_id mismatch")

    # Duplicate or stale (out-of-order older) events: no change.
    if event["event_id"] in state["processed_ids"]:
        return _copy_state(state)
    if event["sequence"] <= state["last_sequence"]:
        return _copy_state(state)

    # Greater sequence but illegal transition: ignored without consuming
    # the sequence or event_id, so it can be retried later.
    if event["new_status"] not in _TRANSITIONS.get(state["status"], frozenset()):
        return _copy_state(state)

    return {
        "payment_id": state["payment_id"],
        "status": event["new_status"],
        "last_sequence": event["sequence"],
        "processed_ids": list(state["processed_ids"]) + [event["event_id"]],
    }
