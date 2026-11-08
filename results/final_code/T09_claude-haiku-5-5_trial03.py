from datetime import datetime, timezone

_RESOLUTIONS = {"resolve_won": "won", "resolve_lost": "lost"}
_TERMINAL = ("won", "lost")


def _parse_utc(value):
    """Parse an ISO8601 aware timestamp and return it as a UTC instant."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"malformed timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"naive datetime not allowed: {value!r}")
    return parsed.astimezone(timezone.utc)


def apply_dispute(dispute: dict, event: dict) -> dict:
    """Apply a dispute event and return a new dispute state.

    Inputs are never mutated. Duplicate event_ids are no-ops that return an
    unchanged copy. Invalid transitions raise ValueError without changing state.
    """
    dispute_id = dispute["dispute_id"]
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    if event.get("dispute_id") != dispute_id:
        raise ValueError("dispute_id mismatch")

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a nonempty string")

    processed_ids = list(dispute["processed_ids"])
    if event_id in processed_ids:
        return {**dispute, "processed_ids": processed_ids}

    action = event.get("action")
    if action not in ("submit_evidence", *_RESOLUTIONS):
        raise ValueError(f"unknown action: {action!r}")

    occurred_at = _parse_utc(event.get("occurred_at"))
    status = dispute["status"]

    if action == "submit_evidence":
        if status != "opened":
            raise ValueError(f"cannot submit evidence when status is {status!r}")
        deadline = _parse_utc(dispute["evidence_deadline"])
        if occurred_at > deadline:
            raise ValueError("evidence submitted after deadline")
        new_status = "evidence_submitted"
    else:
        if status in _TERMINAL:
            raise ValueError(f"dispute already resolved as {status!r}")
        if status != "evidence_submitted":
            raise ValueError(f"cannot resolve when status is {status!r}")
        new_status = _RESOLUTIONS[action]

    return {
        **dispute,
        "status": new_status,
        "processed_ids": processed_ids + [event_id],
    }
