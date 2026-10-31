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
