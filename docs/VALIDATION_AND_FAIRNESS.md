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
