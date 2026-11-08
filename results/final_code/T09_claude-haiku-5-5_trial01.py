from datetime import datetime, timezone

_TRANSITIONS = {
    "submit_evidence": ("opened", "evidence_submitted"),
    "resolve_won": ("evidence_submitted", "won"),
    "resolve_lost": ("evidence_submitted", "lost"),
}
_TERMINAL = ("won", "lost")


def _parse_utc(value, field):
    """Parse an ISO8601 timestamp into an aware UTC datetime; raise ValueError otherwise."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be an ISO8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"malformed {field}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def apply_dispute(dispute: dict, event: dict) -> dict:
    """Apply a dispute event and return a new dispute state.

    Inputs are never mutated. Duplicate event_ids are no-ops returning an
    unchanged copy. Timestamps are compared as UTC instants; the evidence
    deadline is inclusive.
    """
    dispute_id = dispute.get("dispute_id")
    if not isinstance(dispute_id, str):
        raise ValueError("dispute_id must be a string")
    if event.get("dispute_id") != dispute_id:
        raise ValueError("dispute_id mismatch between dispute and event")

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a non-empty string")

    action = event.get("action")
    if action not in _TRANSITIONS:
        raise ValueError(f"unknown action: {action!r}")

    occurred_at = _parse_utc(event.get("occurred_at"), "occurred_at")
    deadline = _parse_utc(dispute.get("evidence_deadline"), "evidence_deadline")

    processed = list(dispute.get("processed_ids", []))
    status = dispute.get("status")

    if event_id in processed:
        result = dict(dispute)
        result["processed_ids"] = processed
        return result

    required_status, new_status = _TRANSITIONS[action]
    if status in _TERMINAL:
        raise ValueError(f"dispute is already terminal: {status}")
    if status != required_status:
        raise ValueError(f"{action} not valid from status {status!r}")
    if action == "submit_evidence" and occurred_at > deadline:
        raise ValueError("evidence submitted after deadline")

    result = dict(dispute)
    result["status"] = new_status
    result["processed_ids"] = processed + [event_id]
    return result
