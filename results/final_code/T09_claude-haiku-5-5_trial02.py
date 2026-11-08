from datetime import datetime, timezone

_RESOLVED = ("won", "lost")
_RESOLUTION_STATUS = {"resolve_won": "won", "resolve_lost": "lost"}


def _parse_utc(value, field):
    """Parse an ISO8601 aware timestamp and return it as a UTC-aware datetime."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"malformed {field}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def apply_dispute(dispute, event):
    """Apply an event to a dispute and return a new dispute dict.

    Inputs are never mutated. Duplicate event_ids are no-ops that return an
    unchanged copy. Invalid events or transitions raise ValueError.
    """
    if not isinstance(dispute, dict) or not isinstance(event, dict):
        raise ValueError("dispute and event must be dicts")

    dispute_id = dispute.get("dispute_id")
    processed = dispute.get("processed_ids")
    if not isinstance(processed, list):
        raise ValueError("processed_ids must be a list")
    status = dispute.get("status")
    if status not in ("opened", "evidence_submitted", "won", "lost"):
        raise ValueError(f"invalid dispute status: {status!r}")

    # Event validation.
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a nonempty string")
    if event.get("dispute_id") != dispute_id:
        raise ValueError("event dispute_id does not match dispute")
    action = event.get("action")
    if action not in ("submit_evidence", "resolve_won", "resolve_lost"):
        raise ValueError(f"unknown action: {action!r}")
    occurred_at = _parse_utc(event.get("occurred_at"), "occurred_at")
    deadline = _parse_utc(dispute.get("evidence_deadline"), "evidence_deadline")

    # Idempotency: replayed events leave the dispute unchanged.
    if event_id in processed:
        return {**dispute, "processed_ids": list(processed)}

    # Transition validation.
    if status in _RESOLVED:
        raise ValueError(f"dispute is terminal ({status}); cannot apply {action}")

    if action == "submit_evidence":
        if status != "opened":
            raise ValueError(f"cannot submit evidence when status is {status}")
        if occurred_at > deadline:
            raise ValueError("evidence submitted after deadline")
        new_status = "evidence_submitted"
    else:
        if status != "evidence_submitted":
            raise ValueError(f"cannot {action} when status is {status}")
        new_status = _RESOLUTION_STATUS[action]

    result = dict(dispute)
    result["status"] = new_status
    result["processed_ids"] = list(processed) + [event_id]
    return result
