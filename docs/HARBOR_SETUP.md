# Harbor execution and validation plan (candidate V2)

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
- Implement and audit bounded, deterministic interleaving tests for T01/T02/T10; don't conflate lock syntax with correctness.
- Freeze artifacts with checksums; record full model IDs, dates, token/cost settings, runtime and raw trajectories.
- Trial results bundled from genuine runs only. None are present in this starter.

## Environment limitation
Harbor and Docker were unavailable while this package was generated. Structural checks and the local Python graders were executed here; Harbor runtime compatibility still needs verification on your machine. See https://github.com/harbor-framework/harbor/blob/main/skills/create-task/SKILL.md .
