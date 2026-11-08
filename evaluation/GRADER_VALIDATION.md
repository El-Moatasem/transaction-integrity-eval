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

The T01, T02 and T10 required graders now use `tests/race_probe.py` to schedule two independent SQLite connections with bounded thread joins. When A pauses after a specified read and has **no** active SQL transaction, B can commit before A resumes. When A holds a transaction that could block B, the probe releases A before waiting for B, avoiding a test-induced deadlock. If an implementation does not use the particular read shape, the test still checks the invariant under two connections without forcing that exact interleaving.

- T01 verifies that competing identical captures debit only once, and rejects a leaked uniqueness error after a conflicting commit.
- T02 verifies the cumulative refund ceiling, credited balance and receipt count after competing 700-cent requests against a 1,000-cent capture.
- T10 verifies that competing debits never overdraw and that inbox, outbox and account balances remain synchronized.
- T03 verifies rollback after a deterministic second-journal-entry failure, followed by successful retry.

**Positive controls:** `audit_variants/T02_atomic_conditional_update.py` uses an independently valid conditional SQL update rather than an explicit `BEGIN IMMEDIATE`. The variant auditor also tests valid deferred `BEGIN` transactions on T01/T02/T10. These ensure the grading checks outcomes instead of a particular lock syntax.

**Negative controls:** `scripts/audit_variants.py` removes transactions entirely from the T01/T02 reference candidates, deliberately commits T03's first journal portion early, and deliberately commits T10's balance/inbox without its outbox. These are specific incorrect behaviors, not a ban on using alternative SQLite transaction syntax.

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
