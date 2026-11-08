# Final calibration runbook — work through this before claiming any result

This runbook is a plan for the participant, **not evidence of completed runs**.

## 1. Clean source baseline

- Run `python scripts/preflight.py`, `python scripts/manifest.py --check`, `python run_eval.py validate`, `python scripts/audit_variants.py`, and `python scripts/repeatability.py --rounds 3`.
- Check each grader assertion against its corresponding `instruction.md`, and read all reference implementations and wrong mutants yourself. Record corrections and why in `results/HUMAN_REVIEW.md`.
- Freeze code, task, grader and manifest hashes before comparative model tests.

## 2. Harbor/Docker smoke tests

- Verify `harbor --version` and `docker info` locally; install a supported Harbor release.
- For each intended task, run Oracle (expected reward 1) and NOP (expected 0). Inspect `/logs/verifier/reward.txt`, pytest log and Harbor output; CLI exit codes alone are not enough.
- Execute tests from the clean source/checkout, not a mutated previously-run workspace.
- Confirm the network policy protects published reference answers. The default task mode is `no-network`, which may block model API access. Configure only provider-specific egress if absolutely required and verify that GitHub/solution mirrors are inaccessible.

## 3. Genuine trial protocol

- Start with pilot tasks **T01, T02, T04**. Pick the model and agent framework intentionally, record exact versions and API endpoint restrictions, and compare identical frozen task/grader versions.
- Run 3–5 **independent clean trials per task per model**. Use fresh model conversations, fresh sandboxes, no earlier workspace contents and no cross-trial memory or hints.
- Save full prompt, model output, tool/action transcript, attempted final code, terminal errors, verified reward and exact time/cost. Do not hand-edit a failing solution to improve its grade and then call that a model pass.
- For local diagnostic trials only, use `run_eval.py prepare`, `grade`, `record`. For Harbor runs preserve native logs and map each genuine run to source checksums.

## 4. Calibration/fairness

- Run positive references and independent valid alternatives, deliberately incorrect examples, failure injection and repeated contention tests.
- Distinguish model error from ambiguously specified task, grader false-fail and infrastructure timeout. A 0% pass rate across all models should trigger an audit, not a claim of frontier-model inability.
- If task/grades are changed after observing model behavior, bump benchmark version and rerun every reported model; avoid selectively dropping good results.

## 5. Human review and reporting

- Fill `results/HUMAN_REVIEW.md` and `results/RESULTS_REPORT.md` with **observed** results and transcript links.
- Generate `results/summary.json` using `python run_eval.py summary --output results/summary.json` after recording the trials.
- Complete README: short description + observed key finding, video URL, exact model IDs/settings, results, failure analysis, cost/runtime, prior work/AI disclosure, and human review.
- Run `python scripts/check_submission.py --strict` and then `python scripts/package_submission.py --out <path>.zip --final`; verify archive opens and is <50 MB. Upload video URL separately and put it in README. Do not include the video in ZIP.

## Suggested video order (<5 min)

~0:00–0:50 domain problem and real cost → ~0:50–2:00 task/spec and grading → ~2:00–3:50 **real results** and one/two transcripts → ~3:50–4:45 conclusions, limitations, reproducibility. Only claim results that logs support.
