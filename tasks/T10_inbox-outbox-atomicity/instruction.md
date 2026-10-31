# T10: Atomic inbox/outbox processing

## Business relevance
A service must not commit a balance change without a corresponding durable outgoing event, nor process the same incoming event twice.

## Requirements
Implement `setup(conn)`, `apply_event(conn,event_id:str,account_id:str,delta_cents:int)->dict`, `get_pending(conn)->list[dict]`, and `mark_published(conn,event_id:str)->None`. setup creates accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER), inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER), outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER). Tests seed accounts. An apply_event requires nonempty event_id/account_id and a nonzero int delta_cents, bool invalid. Use ONE SQLite transaction for inbox dedupe, checking an existing account, preventing negative resulting balance, changing balance, inserting inbox, and inserting outbox. A duplicate event_id with identical account/delta returns its recorded result with no second change; conflicting replay raises ValueError. Return exactly {"event_id":id,"account_id":id,"balance_after_cents":int}. Outbox topic is `account.changed`, published=0, and payload is deterministic JSON with sorted keys and fields event_id, account_id, delta_cents, balance_after_cents. `get_pending` returns a list sorted by event_id, each {"event_id":id,"topic":str,"payload":dict} (decoded JSON). `mark_published` marks an existing outgoing event published=1; repeat is a no-op; unknown event_id raises ValueError. A failure during ANY database write must roll back the entire apply_event transaction. Do not publish to an external service; only manage the durable outbox. Independent SQLite connections may compete; any correct atomic strategy is acceptable.

Concurrent use: each caller supplies an independent SQLite connection with a configured busy timeout. A call encountering an actual database-lock timeout may raise sqlite3.OperationalError without partial changes; a subsequent caller retry must preserve idempotency and all committed invariants. Avoid indefinite blocking.

## Deliverable
Edit only `service.py` in the provided workspace. Keep the public function signatures described above. Use Python 3.11+ standard library only. Outcomes are graded on behavior; any valid implementation is accepted.
