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
