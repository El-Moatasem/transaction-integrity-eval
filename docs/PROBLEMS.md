# Transaction Integrity Eval — Problem Catalog

## Research question
Can coding agents preserve financial transaction invariants not only in the happy path, but also under concurrent requests, repeated operations, reordered messages, interrupted writes, and recovery?

**Status:** These ten problems are original evaluation candidates, not confirmed model failure cases. The full authoritative contract for each lives in `tasks/<task>/instruction.md`.

| ID | Problem | Required invariant | Why it can be challenging |
|---|---|---|---|
| T01 | Idempotent payment capture | Same key and payload never debit twice; conflicting key reuse does not change funds | Debit and receipt must commit together during retries and contention |
| T02 | Partial refund ceiling | Cumulative committed refunds never exceed capture; duplicate requests do not double-credit | Competing individually valid refunds and errors between credit and receipt |
| T03 | Double-entry transfer | Exact minor units and balanced debit/credit entries; atomic writes | Partial postings and conflicting replay requests |
| T04 | Out-of-order webhooks | Only valid transitions consume sequence and event identity; terminal states stay terminal | Early future events may need to be retried after a missing predecessor |
| T05 | Settlement reconciliation | Correct duplicate, missing, unexpected, mismatch, and total accounting | A set-based reconciliation can lose authoritative duplicate-row details |
| T06 | Currency conversion | Exact decimal arithmetic with defined source and target scales; half-even final rounding | Precision boundaries and different currency minor units |
| T07 | Subscription proration | Compute once from actual elapsed UTC seconds with half-even final rounding | Timezone offsets, half-open intervals, and separately rounded portions |
| T08 | Marketplace payout allocation | Conserve every cent and resolve equal remainders deterministically | Tie-breaking, order independence, and fee/net separation |
| T09 | Dispute deadline lifecycle | Honor inclusive UTC evidence deadlines; forbid invalid terminal transitions | Equivalent timestamps with different offsets and duplicate event IDs |
| T10 | Transactional inbox/outbox | Balance, inbox and outbox changes commit atomically; duplicates are idempotent | Failures between writes and competing redeliveries |

## Candidate prioritization

**First pilot:** T01, T02, T04.  
**Second wave:** T03, T05, T10.  
**Reserve:** T06, T07, T08, T09.

Do not exclude successful trials or select tasks solely for low observed scores. Record why a task was retained or excluded based on professional relevance, task clarity, grader reliability, and reproducible model behavior.

## Specific correctness conventions
- T01 and T02 permit safe handling of real SQLite lock contention as defined in their instructions; the grader must not require a particular SQL locking statement.
- T03 represents money in exact minor units, with decimal-string inputs and matching-currency accounts.
- T04 ignores out-of-order *invalid transitions* without consuming their sequence or event ID.
- T05 treats the first duplicate in each input source as authoritative, as the task contract specifies.
- T06 uses `Decimal` and `ROUND_HALF_EVEN`; USD/EUR=2 decimals, JPY=0, KWD=3.
- T07 uses timezone-aware UTC instants, half-open periods, whole seconds, and one final half-even rounding step.
- T08 applies integer largest-remainder allocation with seller-ID lexical tie-breaking.
- T09 compares aware timestamps as UTC instants and uses an inclusive evidence deadline.
- T10 includes the durable outgoing event in the same transaction as the deduplicated balance adjustment.

## Grader reliability and documented limitations
All required behaviors must follow the visible task instructions. Known-correct *alternative* implementations should pass; wrong fixes should fail. Deterministic, bounded concurrency testing for T01, T02 and T10 remains an outstanding improvement. The official micro1 submission must report only genuine, recorded frontier-model trials and observed outcomes.
