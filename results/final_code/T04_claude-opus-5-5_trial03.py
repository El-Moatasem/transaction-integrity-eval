"""Out-of-order payment webhook state machine."""

import copy

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
        raise ValueError("state.payment_id must be a string")
    if state.get("status") not in _STATUSES:
        raise ValueError("state.status is invalid")
    last = state.get("last_sequence")
    if not _is_int(last) or last < 0:
        raise ValueError("state.last_sequence must be a nonnegative integer")
    ids = state.get("processed_ids")
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValueError("state.processed_ids must be a list of strings")


def _validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    if not isinstance(event.get("payment_id"), str):
        raise ValueError("event.payment_id must be a string")
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event.event_id must be a nonempty string")
    seq = event.get("sequence")
    if not _is_int(seq) or seq <= 0:
        raise ValueError("event.sequence must be a positive integer")
    new_status = event.get("new_status")
    if not isinstance(new_status, str) or new_status not in _EVENT_STATUSES:
        raise ValueError("event.new_status is invalid")


def apply_event(state: dict, event: dict) -> dict:
    _validate_state(state)
    _validate_event(event)
    if event["payment_id"] != state["payment_id"]:
        raise ValueError("payment_id mismatch")

    result = copy.deepcopy(state)

    # Duplicate or stale event: no-op.
    if event["event_id"] in state["processed_ids"]:
        return result
    if event["sequence"] <= state["last_sequence"]:
        return result

    # Illegal transition (e.g. arrived before a missing earlier event):
    # ignore without consuming sequence or event_id so it can be retried.
    if event["new_status"] not in _TRANSITIONS[state["status"]]:
        return result

    result["status"] = event["new_status"]
    result["last_sequence"] = event["sequence"]
    result["processed_ids"] = list(state["processed_ids"]) + [event["event_id"]]
    return result
