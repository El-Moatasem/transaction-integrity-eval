# Grader validation and fairness checklist

1. Every assertion in each `tests/test_service.py` must be justified by that task's `instruction.md`.
2. `python run_eval.py validate`: reference passes, flawed baseline fails, alternate incorrect patch fails, for all ten tasks.
3. Independently inspect the ten reference implementations; do not assume AI-generated code is correct merely because it passes local tests.
4. Add further negative implementations, including subtle one-cent, date-edge, reordering, and SQL-rollback errors.
5. Review false-fail risks. Alternative correct algorithms and different code organization must pass.
6. Avoid accidental hidden requirements: paths, signatures and output format must be documented.
7. Use deterministic injection points for gating partial-failure tests. Thread-based concurrent stress tests are supplementary and must be audited for flakiness; unstable/racy graders must be fixed before freezing.
8. Freeze task specifications and graders before measuring models. Hash the files and include the manifest.
9. Keep model-visible workspaces isolated from solutions, tests, and previous workspaces.
10. Collect authentic model transcripts and exact model/runtime/cost details; report negative findings and limitations too.

**Caveat:** These are prototype graders with a baseline and one deliberately incorrect alternative each. Two negative controls are not equivalent to a formal independent false-pass/false-fail analysis.


## Added concurrency regression coverage

The T01, T02 and T10 required graders use `tests/race_probe.py` (three identical copies; `scripts/test_race_probe.py` checks they match) to schedule two independent SQLite connections with bounded thread joins. A SQLite statement-trace hook on connection A pauses A immediately before its **first data-modifying statement** (INSERT/UPDATE/DELETE/REPLACE, including statements behind leading comments and `WITH ... INSERT`). Because the hook is on the connection, it sees SQL issued through `conn.execute()`, `conn.cursor().execute()`, `executemany()` and `executescript()`, independent of SQL spelling or transaction strategy. Connection B then runs for up to 1.5 s; A is always released afterwards (also on errors), so a correct implementation that holds a lock (`BEGIN IMMEDIATE`, or a deferred `BEGIN` whose earlier read holds a SHARED lock) only makes B wait on its busy timeout or makes one side raise a lock-timeout `OperationalError`. Only persisted outcomes are asserted.

Scheduling problems (worker timeout, a pause that was never released, a missing worker outcome) raise `RaceProbeInfrastructureError` with the prefix `RACE_PROBE_INFRA`; `scripts/audit_variants.py` classifies these as INVALID, never as mutation detection. Setting `RACE_PROBE_REPORT=<file>` makes the probe append per-run diagnostics (`a_paused`, `b_started_while_a_paused`, `b_finished_while_a_paused`, pause duration); the audit only credits a concurrency-test rejection when that report shows the intended overlap was exercised.

**Known limitation (documented, not solved):** the pause is at A's *first* write. An implementation that writes, then performs its decisive read, then writes again (for example the T02 counter-based variant, which first inserts a counter row) is paused before the first write, not at the decisive read, so the probe does not guarantee that B commits between that read and the later write. Such code is still graded on persisted outcomes, but a race window located after the first write is not deterministically exercised. No exhaustive SQLite interleaving exploration is performed.

- T01 verifies that competing identical captures debit only once, and rejects a leaked uniqueness error after a conflicting commit.
- T02 verifies the cumulative refund ceiling, credited balance and receipt count after competing 700-cent requests against a 1,000-cent capture.
- T10 verifies that competing debits never overdraw and that inbox, outbox and account balances remain synchronized.
- T03 verifies rollback after a deterministic second-journal-entry failure, followed by successful retry.

**Positive controls:** `audit_variants/T02_atomic_conditional_update.py` uses an independently valid conditional SQL update rather than an explicit `BEGIN IMMEDIATE`. The variant auditor also tests valid deferred `BEGIN` transactions on T01/T02/T10. These ensure the grading checks outcomes instead of a particular lock syntax.

**Negative controls:** `scripts/audit_variants.py` deliberately commits T03's first journal portion early and commits T10's balance/inbox without its outbox. It also generates six candidate controls in temporary workspaces (the committed references are never edited): for each of T01/T02/T10, Variant A deletes `BEGIN IMMEDIATE` without replacement, and Variant B additionally routes every SQL statement through `conn.cursor().execute()`. A rejection counts only when every failing test maps to a documented invariant; syntax/import errors, timeouts and `RACE_PROBE_INFRA` failures are INVALID. A surviving candidate is reported as SURVIVED rather than forced to fail. Results (failing assertion and invariant per variant) are written to `results/mutation_audit.json`. These are specific incorrect behaviors, not a ban on alternative SQLite transaction syntax.

## Remaining expert audit

- Repeat the grader checks in Harbor/Docker, not only local pytest.
- Expand incorrect variants beyond one mutation per task and inspect the actual failure cause.
- Measure grading stability under repeated runs and on supported Python/SQLite versions.
- Confirm hosted coding agents cannot read the reference code or its GitHub history.
- Validate allowed database lock-timeout outcomes and time-bound semantics against the authoritative task instructions.

## Repeatability checks

`python scripts/repeatability.py --rounds 3` reruns reference, starter and wrong-fix controls in fresh workspaces for T01/T02/T10. It is a local smoke/reliability aid, **not** a proof of exhaustive deterministic schedules, nor a substitute for Harbor runs or real agent trial evidence. The race probes use bounded, intentionally scheduled two-connection tests; their coverage and limitations must be disclosed.

## Infrastructure errors are not negative passes

Local control validation only accepts pytest exit code **0** for correct references and exit code **1** (an actual failing assertion) for starter/mutant variants. Pytest collection errors, missing dependencies and timeouts are **not** successful negative controls. A transcript cannot be recorded as a model failure if the grade invocation timed out or failed during setup.
