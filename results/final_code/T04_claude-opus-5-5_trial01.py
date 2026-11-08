STATE_STATUSES = frozenset({"created", "authorized", "captured", "refunded", "cancelled"})
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
    for key in ("payment_id", "status", "last_sequence", "processed_ids"):
        if key not in state:
            raise ValueError(f"state missing {key!r}")
    if not isinstance(state["payment_id"], str):
        raise ValueError("state payment_id must be a string")
    if not isinstance(state["status"], str) or state["status"] not in STATE_STATUSES:
        raise ValueError("invalid state status")
    if not _is_int(state["last_sequence"]) or state["last_sequence"] < 0:
        raise ValueError("state last_sequence must be a nonnegative int")
    ids = state["processed_ids"]
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValueError("state processed_ids must be a list of strings")


def _validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    for key in ("payment_id", "event_id", "sequence", "new_status"):
        if key not in event:
            raise ValueError(f"event missing {key!r}")
    if not isinstance(event["payment_id"], str):
        raise ValueError("event payment_id must be a string")
    if not isinstance(event["event_id"], str) or not event["event_id"]:
        raise ValueError("event_id must be a nonempty string")
    if not _is_int(event["sequence"]) or event["sequence"] <= 0:
        raise ValueError("sequence must be a positive int")
    if not isinstance(event["new_status"], str) or event["new_status"] not in EVENT_STATUSES:
        raise ValueError("invalid new_status")


def _copy_state(state):
    result = dict(state)
    result["processed_ids"] = list(state["processed_ids"])
    return result


def apply_event(state: dict, event: dict) -> dict:
    _validate_state(state)
    _validate_event(event)
    if event["payment_id"] != state["payment_id"]:
        raise ValueError("payment_id mismatch")

    result = _copy_state(state)

    if event["event_id"] in state["processed_ids"]:
        return result
    if event["sequence"] <= state["last_sequence"]:
        return result
    if event["new_status"] not in TRANSITIONS[state["status"]]:
        # Ignored without consuming sequence or event_id; may be retried later.
        return result

    result["status"] = event["new_status"]
    result["last_sequence"] = event["sequence"]
    result["processed_ids"].append(event["event_id"])
    return result
