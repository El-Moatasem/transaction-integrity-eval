> Historical planning note written before the model trials. Final tasks, results and analysis: README.md and results/RESULTS_REPORT.md.

# Pilot protocol: choose 6–8 of the 10 candidates

## Purpose

Identify a **genuine, coherent** failure mode across independent tasks, not a low score from hidden prompt ambiguities. The research claim is *hypothetical* until actual clean trials are recorded.

## Round 1 — independent pilot

1. Freeze `instruction.md`, starter `service.py`, grader tests and the reference implementation for T01, T02, and T04. Record SHA256 checksums.
2. Check grader reference pass, broken starter fail, mutant fail. Conduct an expert review of every asserted behavior, especially transaction failure semantics.
3. Run at least two frontier models, three independent clean trials per model per task (18 total). Fix the total budget before beginning and disclose API/agent access. Use identical frozen task inputs and graders, no mid-trial hints, and clean workspaces.
4. Record complete authentic transcripts, actual model version/settings, runtime/cost and outcome. A task scoring zero across all models requires a grader/spec audit before claiming difficulty.
5. Categorize failures: (a) genuine invariant violation, (b) misread task, (c) grader false fail, (d) environment/tooling failure. Only (a) supports a capability-limit claim.

## Round 2 — choose the final set

- Add T03, T05 and T10 first if they test the same retry/partial-failure pattern. Treat T06, T07, T08 and T09 as reserve candidates if they add explanatory value; purely formulaic tasks may be too easy.
- Keep the pilot results in your provenance, including tasks that were easy or removed. Document selection criteria; do not use only cherry-picked failures.
- Freeze a final benchmark version and rerun every included task against all reported models under identical conditions. Aim for 3–5 trials per task per model.
- Report sample sizes, exact pass/fail outcomes, observed pass-any and pass-all across k trials, plus limitations on uncertainty. Avoid interpreting this small pilot as a general population estimate.

## Fair deterministic testing

- Use database triggers or fault injection to exercise partial-write rollback with the same failure point every trial.
- Separate deterministic correctness tests (gating) from thread-based contention stress tests (secondary/smoke evidence). A passing stress test alone is not proof of correctness, and intermittent stress failures should not define pass/fail until understood.
- Enforce exact contractual invariants, not incidental implementation order or one preferred SQL query.
- Preserve the problem statement and grading hashes alongside trial outputs.

## Go/no-go criteria

Go forward only when (i) each reference is accepted, (ii) several independently wrong implementations are rejected, (iii) no false fails are found during specification review, (iv) at least one genuine failure mode appears in model transcripts, and (v) the end-to-end run reproduces cleanly. A 100% model pass rate means the candidate is not showing an observed limitation; it may still be an excellent engineering exercise.


## Technical rationale and task-by-task probes


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
