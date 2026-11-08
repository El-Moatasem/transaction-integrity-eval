import copy
from datetime import datetime, timezone

_STATUSES = {"opened", "evidence_submitted", "won", "lost"}
_ACTIONS = {"submit_evidence", "resolve_won", "resolve_lost"}


def _parse_aware(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty ISO8601 string")
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"malformed {name}: {value!r}") from exc
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f"{name} must be timezone-aware")
    return dt.astimezone(timezone.utc)


def apply_dispute(dispute: dict, event: dict) -> dict:
    if not isinstance(dispute, dict) or not isinstance(event, dict):
        raise ValueError("dispute and event must be dicts")

    dispute_id = dispute.get("dispute_id")
    if not isinstance(dispute_id, str) or event.get("dispute_id") != dispute_id:
        raise ValueError("dispute_id mismatch")

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a non-empty string")

    processed = dispute.get("processed_ids")
    if not isinstance(processed, list):
        raise ValueError("processed_ids must be a list")

    status = dispute.get("status")
    if status not in _STATUSES:
        raise ValueError(f"invalid status: {status!r}")

    action = event.get("action")
    if action not in _ACTIONS:
        raise ValueError(f"invalid action: {action!r}")

    deadline = _parse_aware(dispute.get("evidence_deadline"), "evidence_deadline")
    occurred = _parse_aware(event.get("occurred_at"), "occurred_at")

    result = copy.deepcopy(dispute)
    result["processed_ids"] = list(processed)

    if event_id in processed:
        return result

    if action == "submit_evidence":
        if status != "opened":
            raise ValueError(f"cannot submit evidence in status {status!r}")
        if occurred > deadline:
            raise ValueError("evidence submitted after deadline")
        new_status = "evidence_submitted"
    else:
        if status != "evidence_submitted":
            raise ValueError(f"cannot resolve dispute in status {status!r}")
        new_status = "won" if action == "resolve_won" else "lost"

    result["status"] = new_status
    result["processed_ids"].append(event_id)
    return result
