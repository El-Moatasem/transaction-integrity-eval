# Transaction Integrity Eval

**A reproducible coding-agent benchmark of financial transaction integrity.**

**Submission state:** implementation and local calibration scaffold complete; **formal Harbor runs, real frontier-model results, human failure analysis and video are PENDING**. This README must be completed with actual experimental evidence before uploading to micro1. Do not describe the hypothesis as a confirmed finding.

## Short description: domain, gap and key finding

The domain is financial-transaction software engineering. This eval tests whether AI coding agents preserve ledger and payment invariants when requests are retried, overlap, arrive out of order, or fail halfway through. Such defects can lead to duplicate charges, excess refunds, missing payouts, or inconsistent account books. **Key empirical finding: RESULTS_PENDING — complete this sentence from genuine model transcripts before final submission.**

## Video walkthrough link

**VIDEO_URL_PENDING** — add a publicly accessible YouTube, Loom, Vimeo or Google Drive URL (no login), maximum five minutes, with audio. Put the same link in the micro1 form. See `evaluation/VIDEO_WALKTHROUGH_TEMPLATE.md`.

## Domain expertise and intended audience

The tasks draw on backend transaction design: payment idempotency, relational transaction boundaries, double-entry journals, settlement matching, integer/decimal money arithmetic, sequence-numbered event handling and audit trails. Intended readers include payments engineers, risk engineers, backend reviewers and coding-agent researchers. A failure matters because a plausible implementation can silently corrupt money-related state during a retry or partial write.

## Tasks and scoring

Ten independent candidates, each with a precise `instruction.md`, an intentionally flawed `environment/service.py`, reference solution, deliberately incorrect mutant, and a pytest grader:

| Task | Problem | Important invariant |
|---|---|---|
| T01 | Payment capture | Same idempotency key cannot debit twice |
| T02 | Refund ceiling | Cumulative refunds cannot exceed a capture |
| T03 | Double-entry transfer | Debit/credit balance and atomic posting |
| T04 | Webhook ordering | Only legal state changes consume events |
| T05 | Settlement reconciliation | Duplicate, missing, unexpected and mismatched rows distinguished |
| T06 | FX rounding | Exact decimal conversion with target currency scale |
| T07 | Subscription proration | UTC elapsed-second proportional charge with one final rounding |
| T08 | Marketplace splits | Every cent conserved with deterministic remainders |
| T09 | Dispute deadlines | Inclusive UTC deadlines; terminal state cannot reopen |
| T10 | Transactional inbox/outbox | Balance, inbox and outbox commit together |

Reward **1** means all task assertions pass; **0** means at least one fails. No LLM-as-judge is used. The score reflects the final code behavior, not the text of the response or use of a preferred SQL syntax. See [`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md) for problem details and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the trust boundary.

## Dependencies and clean setup

Requires Python 3.11+ for local checks, pinned `pytest==9.0.2`, and Python 3.12 in the provided task Docker images. Harbor and Docker are required only for the intended formal agentic execution. No API key is needed for local checks; hosted-model keys are supplied externally as environment variables documented in `.env.example` **without committing values**.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/preflight.py
python scripts/manifest.py --check
python run_eval.py validate
python scripts/audit_variants.py
python scripts/repeatability.py --rounds 2
python scripts/package_submission.py --check
```

**Time/cost:** Local validation depends on the host and should be measured on the judge's machine; no cloud model fees are required for these checks. A full live run costs the sum of the provider's actual per-trial token charges, which must be recorded rather than guessed. Fill in measured runtime and approximate provider cost after the pilots. The local runner executes agent-generated code without a security sandbox; run only trusted patches locally.

## Harbor Oracle and NOP (needs working Docker)

```bash
harbor --version && docker info
harbor run -p tasks/T02_refund-ceiling -a oracle
harbor run -p tasks/T02_refund-ceiling -a nop
```

Repeat Oracle and NOP for each selected final task, then run real model trials using a supported agent/model. Verify API access is compatible with the default `no-network` policy or a restricted egress allowlist **without public GitHub solution access**. See `evaluation/REPRODUCIBILITY.md` and `evaluation/CALIBRATION_RUNBOOK.md`. Neither Harbor success nor isolation has been verified in this generated package.

## Run a manual isolated diagnostic trial

```bash
python run_eval.py prepare --task T01 --output /tmp/txn-T01-trial-01
# Give your agent ONLY that directory and INSTRUCTION.md. Save the real transcript.
python run_eval.py grade --task T01 --workspace /tmp/txn-T01-trial-01 --output /tmp/T01-grade.json
python run_eval.py record --task T01 --model '<model-family>' --version '<exact-model-id>' \
  --trial 1 --transcript /path/to/authentic-transcript.txt \
  --grade-json /tmp/T01-grade.json --settings '{"temperature":0}' \
  --runtime "$MEASURED_RUNTIME_SECONDS" --cost "$MEASURED_COST_USD" --agent '<agent-and-version>'
python run_eval.py summary --output results/summary.json
```

Set `MEASURED_RUNTIME_SECONDS` and `MEASURED_COST_USD` from the authentic provider/agent run before recording; the recorder cannot verify provider billing or transcript provenance. Never expose the reference solution, graders, mutants, other trials, or repository root to the evaluated agent. For genuinely isolated model trials use Harbor, retaining complete logs and transcripts.

## Models tested and results

**RESULTS_PENDING.** No frontier-model attempts were run for the distribution. Fill the table with exact model IDs, versions, temperature/reasoning settings, dates, tasks, number of trials, scores, runtime and cost. Include at least two models if possible; the guide asks for at least one frontier model and multiple independent trials per task. Run 3–5 trials per task as a starting point.

| Model (exact ID) | Date UTC | Agent/version | Settings | Tasks | Trials per task | Pass rate | Observed pass@k / pass^k | Runtime | Cost |
|---|---|---|---|---|---|---|---|---|---|
| *Complete after genuine trials* | | | | | | | | | |

`python run_eval.py summary` reports observed outcomes; it does not estimate population success probabilities from sparse data. Preserve authentic `results/trials.jsonl`, `results/grades/`, `transcripts/`, and a human-reviewed `results/RESULTS_REPORT.md`. See `evaluation/RESULTS_REPORT_TEMPLATE.md`.

## Failure analysis and key insight

**FAILURE_ANALYSIS_PENDING.** For each observed model failure, cite the transcript and explain the violated invariant, the exact final-state error, and why the task instruction justified the grader's expectation. Check for false failures and report any task on which all models succeed. **HOT_TAKE_PENDING:** derive this only from observed patterns; do not invent limitations.

## Grader reliability

Every task has a reference-positive, starter-negative and mutant-negative control; independent positive and additional negative variants check fairness. The bounded multi-connection tests on T01/T02/T10 are regression probes, not a proof that all concurrent schedules are covered. Locally recorded controls are not substitutes for Oracle/NOP inside Harbor. Any prompt/grader modification after seeing model results requires recording a new benchmark version and rerunning comparable models.

## Prior work, sources and use of AI

The project is an original synthetic Python/SQLite evaluation scaffold first developed during the 2026 micro1 hackathon, using general principles of financial transaction correctness. It does not intentionally incorporate private client or employer code or licensed proprietary datasets. The Harbor task layout follows publicly documented Harbor/Terminal-Bench patterns (see `evaluation/REPRODUCIBILITY.md`). AI coding assistance was used to draft parts of the scaffold, tests and documentation. **HUMAN_REVIEW_PENDING:** before final submission, describe your actual independent checks and corrections of every reference implementation, grader assertion and accounting convention. Do not claim review you have not performed.

## Submission readiness and packaging

```bash
python scripts/check_submission.py
# After genuine trials + video + human review + completed README:
python scripts/check_submission.py --strict
python scripts/package_submission.py --out /tmp/transaction-integrity-eval-submission.zip --final
```

Official micro1 format: one ZIP under 50 MB with this README at the ZIP root; a publicly accessible **≤5-minute audio video** linked in the README and form; a short description in both places; the task inputs/expected outcomes and graders; genuine raw model outputs, model IDs, settings, scores, and source/provenance. No videos, secrets, confidential materials or third-party content without rights inside the ZIP. The official deadline shown in the participant instructions is **November 9, 2026, 05:15 GMT**. Only the latest completed submission is evaluated.
