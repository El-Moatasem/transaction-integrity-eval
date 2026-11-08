# Reproducing the benchmark


## Tooling
- Python 3.12+ to install the current Harbor CLI (separate from the benchmark's Python 3.12 runtime).
- Docker Desktop or Docker Engine must be running.
- Install Harbor with `uv tool install harbor` (recommended) or follow upstream instructions.
- `harbor --version` and `docker info` must both succeed.
- Python package `pytest==9.0.2` is installed in each task's Dockerfile; the verifier itself does not fetch dependencies.

## Preflight and controls
```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/preflight.py
python run_eval.py validate
python scripts/audit_variants.py
python scripts/repeatability.py --rounds 3
python scripts/manifest.py --check
harbor run -p tasks/T01_capture-idempotency -a oracle
harbor run -p tasks/T01_capture-idempotency -a nop
```
The Oracle expected outcome is 1; no-op expected 0. Repeat on each task with a run script or shell loop.

## Real agent tests
```
harbor run -p tasks/T02_refund-ceiling -a mini-swe-agent -m '<provider/exact-model-id>'
```
Choose an actual exact model ID supported by your provider, configure its credentials via the provider's documented environment variables, and verify the flags against `harbor run --help`. For formal comparisons, use the same agent framework, per-task timeouts, grader version and prompts; vary the model only. Report Claude Code or Codex CLI agent runs as separate agent configurations unless appropriately controlled.

## Artifact isolation and disclosure
Harbor makes `/solution/` available only for the oracle and `/tests/` for verification; the Dockerfile copies only `service.py`. Do not mount the repository root into an agent container. Keep all reference implementations, mutants, and graders out of the task's agent-visible image. The evaluation ZIP may contain all artifacts for judge reproduction; Harbor controls their availability by phase.

## Acceptance criteria before formal model claims
- Run actual Harbor oracle and no-op trials for every frozen task.
- Verify reward and verifier logs from the jobs directory.
- Prove correct alternative implementations pass and wrong-fix variants fail.
- Review the current bounded, intentionally scheduled two-connection tests on T01/T02/T10 and extend them if necessary; avoid treating lock syntax as correctness.
- Freeze artifacts with checksums; record full model IDs, dates, token/cost settings, runtime and raw trajectories.
- Trial results bundled from genuine runs only. None are present in this starter.

## Environment limitation
Harbor and Docker were unavailable while this package was generated. Structural checks and the local Python graders were executed here; Harbor runtime compatibility still needs verification on your machine. See https://github.com/harbor-framework/harbor/blob/main/skills/create-task/SKILL.md .


## Submission limitation

Do not claim Harbor/Docker success or real model performance until the commands have been run, logs inspected, and exact commit/checksums recorded.

## Agent network policy

The default task network mode is `no-network`, which protects trial isolation but may also prevent hosted coding agents from contacting an LLM API. For real model trials, explicitly configure a **verified provider-specific allowlist** (and no access to GitHub, raw.githubusercontent.com, or other answer mirrors), or another proven isolation mechanism. Harbor supports `public`, `no-network`, and `allowlist`; plain Docker cannot dynamically switch phase network policies. Do not use a public network baseline while claiming blind answer isolation.

## Cross-platform integrity verification

```bash
python scripts/manifest.py --check
python scripts/audit_variants.py
```

Regenerate `manifests/SOURCE.sha256` after intended changes with `python scripts/manifest.py --write`; compare full source hashes, not stale ZIP hashes.

## Build and network caveats

The task Dockerfiles install pinned `pytest` in the image. If the container build cannot reach its dependency source, pre-build the environment in an authorized networked build step or configure scoped installation endpoints; do not silently broaden the model-facing runtime network. A `no-network` policy can prevent hosted LLM CLI tools from contacting their provider. Verify actual task-runner behavior with the chosen provider before reporting model scores.

Do not interpret an agent's access to a published GitHub solution as a legitimate independent solution, regardless of the local network policy.


## Code-ready versus final submission

The distributed baseline is **ready for local grading/calibration**, not yet a complete micro1 submission. To become eligible under the participant guide it still needs genuine model transcripts, per-model scores/settings, judge-reproducible results, participant expert review, a short description, and a publicly accessible video URL with audio. The `check_submission.py --strict` gate explicitly requires these, and `package_submission.py --final` refuses to produce a final ZIP otherwise. Do not place Git-flow/PR instruction files inside the project package.

## Claude Code CLI trial runner

`scripts/run_claude_trials.py` runs headless `claude -p` trials and records them through `run_eval.py record`. Check it without any model call:

```bash
python scripts/run_claude_trials.py --help
python scripts/run_claude_trials.py --models <exact-model-id> --tasks T01,T10 --trials 1 --dry-run
python -m unittest discover -s scripts -p 'test_trial_runner.py'   # stub CLI in a temp repo copy; aborts unless `claude` resolves to the stub
```

What it guarantees:

- Each trial gets a fresh temporary workspace outside the repository containing only `INSTRUCTION.md` and the starter `service.py` (no reference solution, mutants, hidden tests, Git history or other trials).
- Missing `result` events, non-zero CLI exits, `is_error` results (authentication, rate limit, overload), crashes, timeouts and grader infrastructure errors are reported as `[INFRA - not recorded]` and are never recorded as model failures. Rerun to retry.
- Recorded settings include the requested and CLI-reported model, CLI version, tool policy, turn limit, runtime and cost; the record adds transcript, code and grader SHA-256 hashes and repository-relative transcript/grade paths.
- A genuine CLI result event with `subtype == "error_max_turns"` is classified **before** the generic `is_error`/non-zero-exit check as a model attempt that exhausted its turn budget, not an infrastructure failure. Its final `service.py` is graded by the normal grader and recorded with its real pass/fail outcome; the subtype never decides the score. Settings record `stop_subtype`, `max_turns` and `turn_budget_exhausted: true`. If such an attempt cannot be graded (no report, or a grader exit other than 0/1), its transcript, final code, runtime and cost are preserved under `results/incomplete/` and listed in `results/incomplete_attempts.jsonl` with `status: incomplete` and no score; it is excluded from `trials.jsonl` and pass rates, and its trial slot is not re-run on resume.
- Already-recorded (task, model, agent, trial) combinations are skipped, and `record` refuses to overwrite existing evidence, so interrupted batches resume safely.
- Record operations are serialized by a process-local `threading.Lock` in the runner and an exclusive `fcntl` file lock (`results/.trials.lock`) inside `run_eval.py record`, so parallel workers and concurrent POSIX processes cannot interleave the duplicate check, evidence copy and JSONL append. On Windows (no `fcntl`) only the thread lock applies: do not run two batches at once there.

What it does **not** guarantee (workspace isolation is not network or filesystem isolation):

- Disabling `WebFetch`/`WebSearch` does not block the network. The agent keeps the `Bash` tool, which can run `curl`, `wget`, `git clone`, `pip install` or Python `urllib`. No network sandbox is applied.
- `Bash` runs as your OS user and can read any path you can, including this repository and its reference solutions.
- The CLI still loads your user-level Claude Code settings and `CLAUDE.md` unless you pass `--bare` (which requires `ANTHROPIC_API_KEY`). MCP servers are skipped with `--strict-mcp-config`.
- After each batch (or with `--audit-only`) the runner scans every recorded transcript's tool calls for indicators (`github`, `curl`, `wget`, `urllib`, `requests`, `pip install`, URLs, this repository's path, `solution/`/`mutants/` paths) and writes `results/network_audit.json`. Flagged trials need human review; a flag is not proof of contamination, and no flag is not proof of isolation, because command-string scanning cannot detect every network or file access.
