# Transaction Integrity Eval

**Status:** Original prototype benchmark; not yet validated on frontier models. Do not claim measured model limitations until real trials have been run and audited.

**Research hypothesis:** models may preserve financial invariants on the happy path while violating them under concurrent operations, retries, reordered events, partial writes and recovery. This is a hypothesis until genuine model trials establish it.

A small, offline-first coding-agent benchmark for reliability of money movement systems. Ten separate Python tasks cover payment captures, refunds, ledgers, webhooks, reconciliation, FX, proration, split payouts, dispute deadlines and transactional inbox/outbox patterns. The problem statements are designed around production invariants, not trick questions. No AgentGuard or Askable project code, hidden tests or solutions are copied.

## Layout

- `tasks/T01_.../` to `tasks/T10_.../`: independently runnable tasks.
- `instruction.md`: complete agent-visible task and behavioural contract.
- `environment/service.py`: deliberately incomplete or flawed starter implementation, shown to agents.
- `environment/Dockerfile`: Harbor agent container image, without grader or reference.
- `solution/service.py` and `solution/solve.sh`: Oracle reference *candidate*; held back from agents.
- `tests/test_service.py` and `tests/test.sh`: code-based grader and Harbor reward script; withheld until verification.
- `mutants/service.py`: intentionally wrong alternative used to check the grader.
- `run_eval.py`: local controls, clean workspaces and offline grading.
- `results/`: validation and manually recorded REAL trial metadata. `trials.jsonl` starts absent.
- `transcripts/`: place only transcripts captured from actual model executions.

## Candidate selection and fairness

Ten **candidates** are packaged; pilot T01, T02 and T04 first, then select the best 6–8 for the final evaluation. See `docs/PILOT_AND_SELECTION.md` and `docs/TASK_RESEARCH_RATIONALE.md` for adversarial probes and transparent selection rules. Task specifications explicitly pin rounding and time conventions; do not add hidden behaviors when grading.

## Requirements and validation

Python >=3.11 and pytest 9.0.2 (see `requirements.txt`). Harbor + Docker is the intended formal agentic evaluation runner; the existing local harness remains a smoke-test and diagnostic runner. Harbor requires a compatible installation and a working container runtime. Neither Harbor nor Docker was available in the file-generation environment, so Harbor Oracle/NOP runs are not claimed as completed. The local runner is NOT a security sandbox.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_eval.py validate
```

All 10 reference solutions must pass, and all 10 original starter code implementations and 10 deliberately wrong fixes must fail. This is a minimum smoke test, not proof the grader has zero false positives or false negatives.

## Harbor + Docker (intended formal harness)

See `docs/HARBOR_SETUP.md`. Each task now includes Harbor-style `task.toml`, Dockerfile, Oracle `solution/solve.sh`, and `tests/test.sh` which writes `/logs/verifier/reward.txt`. Install Harbor using Python 3.12+ and launch Docker on your own machine. The output should be verified locally first:

```bash
python scripts/preflight.py
harbor run -p tasks/T02_refund-ceiling -a oracle
harbor run -p tasks/T02_refund-ceiling -a nop
harbor run -p tasks/T02_refund-ceiling -a mini-swe-agent -m '<provider/exact-model-id>'
```

**Not yet tested end-to-end in Docker/Harbor**; these commands are the next user-run acceptance gate.

## Run an independent agent trial (fallback local harness)

```bash
python run_eval.py prepare --task T01 --output /tmp/txn-t01-trial1
# Open /tmp/txn-t01-trial1 in your AI coding agent; send INSTRUCTION.md as the task prompt.
# Save its real transcript elsewhere. DO NOT point the agent at the benchmark root.
python run_eval.py grade --task T01 --workspace /tmp/txn-t01-trial1 --output /tmp/t01-grade.json
python run_eval.py record --task T01 --model 'your-model' --version 'exact-id' \
  --trial 1 --transcript /path/to/real-transcript.txt --grade-json /tmp/t01-grade.json \
  --settings '{"temperature":0}' --runtime 85 --cost 0.14
python run_eval.py summary
```

Use fresh workspaces and fresh model conversations for every trial. Do not reuse agent history or permit the agent to read `solution/`, `mutants/`, `tests/`, `results/`, or other tasks. Agents should work only in their isolated workspace. The grader runs after the attempt and copies tests into another temporary directory. No automatic network-based model API runner is included, so no trial numbers or scores are fabricated.

## Grading and model comparison

Each task uses objective pytest behavioral assertions. T01/T02 optional `tests/stress_test_service.py` files provide supplementary thread contention probes; these are not part of the deterministic gating grader. The baseline score is pass/fail per task/trial. After running 3-5 independent trials per task on each model, compute observed per-task pass rate, empirical all-k (pass^k) and any-k (pass@k), and record sample sizes. Don't compare model families using trials with different instructions or graders. The repository does NOT include real model-trial evidence as delivered.

## Evidence, provenance and publication

This repo contains fresh, synthetic scenarios and code drafted with AI assistance on 2026-10-30, and must be carefully reviewed by the participant. No prior proprietary project code, confidential payment data, private Askable benchmark material, or real API keys are included. Before submitting, manually confirm every task spec matches its grader, add varied wrong-fix tests, run at least one frontier model several times, read the transcripts, report failures honestly, and document exact model versions/settings, trial times, costs and provenance.

The official micro1 event Instructions tab takes precedence over this scaffold and local documentation. ZIP up only permitted code/supporting files (<50 MB), and provide the required video (<=5 minutes) and description separately.

## Known risks and remaining work

- The initial 10 tasks are **candidates**, not validated frontier-model failures. No real agent trials were run here.
- T01/T02/T10 have basic failure-injection controls, but **a fully calibrated, deterministic, multi-connection concurrency grader is still outstanding**. Do not claim it is complete.
- The alternative T02 reference in `docs/alternative_solutions/` demonstrates a valid deferred-transaction + atomic conditional update approach. It must pass the same grader.
- The frozen final model comparison must use an unchanged, independent grader. Harbor's agent/model combination must be documented exactly.
- SQLite makes the eval offline/reproducible; its locking semantics differ from PostgreSQL and this benchmark does not claim database-engine equivalence.
