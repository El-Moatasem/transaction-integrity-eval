# Research hypothesis and why the tasks are hard

**Hypothesis, not a finding:** coding agents often preserve business invariants in ordinary operations but lose those invariants under replays, reordering, partial writes or failures. This has not been demonstrated on frontier models in this prototype.

**Selection strategy:** keep all 10 candidates in the project and pilot T01, T02, T04 first; then select 6-8 benchmark tasks based on real trials, *without* cherry-picking individual examples that suit a narrative. Record excluded candidates and reasons.

| ID | Priority | Interaction that creates difficulty | Planned adversarial probe |
|---|---|---|---|
| T01 | PILOT | An idempotency record must be committed with its debit; a failure after debiting but before writing the receipt must not lose money. | Inject failure on receipt insertion after balance update; verify full rollback and safe replay on a fresh connection. |
| T02 | PILOT | Two individually valid refunds may jointly exceed the original charge; a failure between balance credit and refund record must not create free money. | Inject failure after balance update and before refund insertion; verify rollback plus cumulative ceiling under contention. |
| T03 | SECOND WAVE | Correct arithmetic can still produce unbalanced journals after partial writes or conflicting retry payloads. | Force second journal insertion failure and verify all-or-nothing posting, then retry with conflicting fields. |
| T04 | PILOT | A later event can arrive before an earlier event, and discarding it as processed too early makes legitimate recovery impossible. | Deliver future capture before authorization, then missing authorization, then replay capture; inspect consumed IDs/sequence. |
| T05 | SECOND WAVE | Reconciling duplicated identifiers using a plain set loses which row was authoritative and can hide net differences. | Combine same-ID duplicates, pending ledger entries, missing settlements and mismatched fees with totals. |
| T06 | LOWER PRIORITY | Cross-currency minor-unit scales and half-even ties can make a numerically plausible conversion off by one smallest unit. | Vary source/target precision, tie directions, trailing zeros and invalid amount types. |
| T07 | LOWER PRIORITY | Billing changes near a timezone transition can be mispriced when elapsed days replace elapsed UTC seconds or components round separately. | Use fixed aware instants spanning offset changes and an exact tie that must round only once. |
| T08 | LOWER PRIORITY | A one-cent remainder may be allocated inconsistently when weight ordering or ties change. | Permute input seller order and test adversarial ties and fee subtraction; future extension: proportional refund reversals. |
| T09 | LOWER PRIORITY | An equality-boundary deadline expressed with a different UTC offset can be incorrectly rejected or a terminal dispute reopened. | Test equivalent instants, exactly-on-deadline submission, replay after terminal resolution and invalid naive timestamps. |
| T10 | SECOND WAVE | An account update may commit while its outgoing event fails, producing silent divergence; dedupe must share that transaction. | Inject an outbox write failure after the balance/inbox write; verify full rollback and replay consistency. |

## Task selection / contamination safeguards

- Pilots inform feasibility and whether a capability gap is plausible. Do not continue modifying tasks simply to drive a favored model score down.
- If a specification or grader is repaired after inspecting model attempts, log the reason, create a new benchmark version, and retest all comparison models on that exact frozen version.
- For T06/T07/T09, all currency scales, rounding modes, timezone treatment, inclusion rules and error behavior appear in the task prompt.
- No task incorporates source, tests, golden patches or private materials from Askable/AgentGuard.
- A self-contained project authored with AI still requires the participant to check accounting rules, tests and code before submitting.
