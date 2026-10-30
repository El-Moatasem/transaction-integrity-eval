# T04: Out-of-order payment webhook state machine

## Business relevance
Webhook arrival order does not imply transaction transition order, and terminal states cannot be reopened.

## Requirements
Implement `apply_event(state: dict,event: dict)->dict`. Both input dictionaries must remain unchanged. State shape: {"payment_id": str,"status": one of created|authorized|captured|refunded|cancelled, "last_sequence": nonnegative int,"processed_ids": list[str]}. Event shape: {"payment_id": str,"event_id": nonempty str,"sequence": positive int,"new_status": one of authorized|captured|refunded|cancelled}. Valid transitions only: created->authorized, created->cancelled, authorized->captured, authorized->cancelled, captured->refunded. `refunded` and `cancelled` are terminal. For an already processed event_id or an event whose sequence <= last_sequence, return an unchanged copy. If the next event has a legal transition and strictly greater sequence, return a fresh state with new status/last_sequence and event_id appended. An event with a greater sequence but invalid state transition is ignored WITHOUT consuming sequence or event_id, so it may be retried after missing earlier events. A payment_id mismatch or malformed event raises ValueError, inputs unchanged. Invalid events do not advance state.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
