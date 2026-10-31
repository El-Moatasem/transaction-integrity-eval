# T09: Dispute lifecycle and inclusive UTC deadline

## Business relevance
Deadlines can be accidentally shifted by timezone parsing, and idempotency must not reopen resolved disputes.

## Requirements
Implement `apply_dispute(dispute: dict,event: dict)->dict`. Dispute state {"dispute_id":str,"status":"opened"|"evidence_submitted"|"won"|"lost", "evidence_deadline": ISO8601 aware timestamp, "processed_ids":list[str]}. Event {"dispute_id":str,"event_id":nonempty str,"action":"submit_evidence"|"resolve_won"|"resolve_lost","occurred_at":ISO8601 aware timestamp}. Return a NEW dictionary with a NEW processed_ids list, never mutate inputs. Duplicate event_id is a no-op returning unchanged copy. `submit_evidence` only valid when status opened and occurred_at <= evidence_deadline (inclusive) comparing UTC instants. Resolutions only valid after evidence_submitted; resolution timestamps can exceed the evidence deadline. Resolved states won/lost are terminal; other transitions raise ValueError without change. Mismatched IDs, malformed timestamps or naive datetimes raise ValueError. Accepted events append event_id and set status; do not use current system time.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
