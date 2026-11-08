# Transaction Integrity Eval

**A reproducible coding-agent benchmark of financial transaction integrity.**

**Submission state:** 147 recorded Claude Code CLI trials across 14 tasks and 3 models are reported below and in [`results/RESULTS_REPORT.md`](results/RESULTS_REPORT.md). The video walkthrough and the author's human review are still outstanding. Formal Harbor/Docker runs were not performed.

## Short description: domain, gap and key finding

The domain is financial-transaction software engineering. This eval tests whether AI coding agents preserve ledger and payment invariants when requests are retried, overlap, arrive out of order, or fail halfway through. Such defects can lead to duplicate charges, excess refunds, missing payouts, or inconsistent account books.

**Key finding** *(DRAFT — author to rewrite)*: Across 147 Claude Code trials on Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5, **every race test passed**. That held even when the concurrency requirement was only implied by a deployment fact (T11–T13), and when a bug report pointed at one of three write paths that all needed protection (T14). The only two failures (2/147, both on T14) were **transaction-lifecycle bugs**, not missing locks: one replay branch returned while its `BEGIN IMMEDIATE` was still open, and one rollback helper committed the partial write before rolling back. In this setup the models reliably knew *to* lock; what they occasionally got wrong was ending the transaction correctly on every exit path.

## Video walkthrough link

**VIDEO_URL_PENDING** — add a publicly accessible YouTube, Loom, Vimeo or Google Drive URL (no login), maximum five minutes, with audio. Put the same link in the micro1 form. See `evaluation/VIDEO_WALKTHROUGH_TEMPLATE.md`.

## Domain expertise and intended audience

The tasks draw on backend transaction design: payment idempotency, relational transaction boundaries, double-entry journals, settlement matching, integer/decimal money arithmetic, sequence-numbered event handling and audit trails. Intended readers include payments engineers, risk engineers, backend reviewers and coding-agent researchers. A failure matters because a plausible implementation can silently corrupt money-related state during a retry or partial write.

## Tasks and scoring

There are fourteen tasks. Each has a precise `instruction.md`, an intentionally flawed `environment/service.py`, a reference solution, a deliberately incorrect mutant, and a pytest grader. T01–T10 are the core tasks. T11–T13 are instruction-only ablations of T01, T02 and T10. T14 tests multiple write paths that share one invariant.

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
| T11 | Payment capture, implicit (ablation of T01) | Same as T01 |
| T12 | Refund ceiling, implicit (ablation of T02) | Same as T02 |
| T13 | Inbox/outbox, implicit (ablation of T10) | Same as T10 |
| T14 | Refund write paths | Committed refunds never exceed the *current* captured amount, and no refund commits after a void, across `refund`, `adjust_capture` and `void_remaining` |

**T11–T13** share their environment, reference, mutant and tests byte-for-byte with T01, T02 and T10; only `instruction.md` differs. The rewritten instructions keep every graded behavior but drop any mention of races, concurrency, transactions, atomic strategies or locking. Instead they state the invariants as absolute rules and add one deployment fact: "This service runs on several worker processes; each call uses its own SQLite connection." This measures whether the concurrency requirement is inferred rather than read.

**T14** opens with a bug report ("customers were refunded more than was captured") followed by the full contract for three functions. All three read before they write, but the report names only refunds. The wrong-fix mutant protects only `refund()`. The race tests run refund against adjustment and refund against void in both orders, so a fix to only one side cannot pass.

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

There were 147 recorded trials, with **145 passed**. All of them are reported; none were excluded. The transcript audit flagged **0 of 147** trials for network or answer-key access. Full details, chronology and evidence paths are in [`results/RESULTS_REPORT.md`](results/RESULTS_REPORT.md).

| Model (exact ID) | Date UTC | Agent/version | Settings | Tasks | Trials per task | Pass rate | Observed pass@k / pass^k | Runtime | Cost |
|---|---|---|---|---|---|---|---|---|---|
| `claude-opus-5-5` | 2026-11-08 | Claude Code CLI 2.1.319 | CLI default temperature; max 40 turns; tools Read/Edit/Write/Bash; no web tools or MCP | T01–T14 | 3 (T14: 10) | 48/49 | 1 / 1 on all tasks except T14 (1 / 0) | 2,509 s | $9.77 |
| `claude-sonnet-5-5` | 2026-11-08 | Claude Code CLI 2.1.319 | same | T01–T14 | 3 (T14: 10) | 48/49 | 1 / 1 on all tasks except T14 (1 / 0) | 785 s | $3.15 |
| `claude-haiku-5-5` | 2026-11-08 | Claude Code CLI 2.1.319 | same | T01–T14 | 3 (T14: 10) | 49/49 | 1 / 1 on all tasks | 1,241 s | $0.32 |

Runtime and cost are totals across each model's 49 trials, as reported by the CLI.

| Task group | What the instruction says | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|---|
| T01–T10 (baseline) | Explicit contract, including the concurrency requirement where relevant | 30/30 | 30/30 | 30/30 |
| T11–T13 (ablation of T01/T02/T10) | Same tests; no mention of races, concurrency, transactions or locking, only absolute invariants plus "several worker processes; each call uses its own SQLite connection" | 9/9 | 9/9 | 9/9 |
| T14 refund write paths | Bug report about over-refunds plus the full contract for `refund`, `adjust_capture` and `void_remaining`; all three must be protected | 9/10 | 9/10 | 10/10 |

**Chronology:**
1. The T01–T10 baseline.
2. The T11–T13 ablation.
3. T14 with 3 trials per model.
4. After the first T14 failure, T14 was extended to 10 trials per model.

The T14 instruction and grader were identical for all 30 T14 trials. Race tests (in T01, T02 and T10–T14) passed in all 84 trials that contain them.

`python run_eval.py summary` reports observed outcomes; it does not estimate population success probabilities from sparse data. Preserve authentic `results/trials.jsonl`, `results/grades/`, `transcripts/`, and a human-reviewed `results/RESULTS_REPORT.md`. See `evaluation/RESULTS_REPORT_TEMPLATE.md`.

## Failure analysis and key insight

*(DRAFT — author to rewrite)* Both failures are on T14 and come from sequential tests, not race tests. Both failing solutions put `BEGIN IMMEDIATE` on all three write paths and passed all four T14 race tests. The exact code excerpts and grader output are in [`results/RESULTS_REPORT.md`](results/RESULTS_REPORT.md#the-two-failures).

- **Sonnet 5.5, T14 trial 3.** In `refund`, the exact-replay branch returned the stored receipt from inside an open `BEGIN IMMEDIATE`, without committing or rolling back. The replay looked correct. However, the connection still held its write lock and an open transaction, so the next call on it raised `sqlite3.OperationalError: cannot start a transaction within a transaction`. That broke a conflicting-key refund and an adjustment of a voided capture, both of which must raise `ValueError`. The contract allows `OperationalError` only when the database is busy.
- **Opus 5.5, T14 trial 8.** A `_rollback` helper first called `_begin`, which commits any open transaction before starting a new one. When the refund-receipt `INSERT` failed, the balance credit was therefore committed, and the following rollback had nothing left to undo. The final state was `credited: 200` against an expected `0`: a credit with no receipt, violating "a call that raises leaves the database unchanged" and the credit/receipt invariant.

Neither failure is a false failure. Each maps to an explicit contract sentence and shows up as a wrong exception type or wrong persisted state. On 13 of the 14 tasks, all three models passed every trial.

**Hot take** *(DRAFT — author to rewrite)*: For these models, "did you remember to lock?" was never the problem in our runs; across 84 trials with race tests, none failed one. Both bugs that did get through sat on the *exits* of a correctly opened transaction: an early return and an error path. Neither would ever show up in a race test. A grader that only checks for the race overstates how correct the code is. Transaction code needs tests that leave the transaction by every route: replay, conflict, injected failure, and the call that follows. This is a two-failure sample, so treat it as a hypothesis worth testing at larger n, not a measured rate.

## Grader reliability

Every task has three controls: the reference must pass, and the starter and the mutant must fail. All 14 tasks pass these controls (`results/validation.json`). `scripts/repeatability.py --rounds 3` reproduces all 63 expected control outcomes on the race tasks.

**Race probe.** T01, T02 and T10–T14 use a race probe (`tests/race_probe.py`). It hooks SQLite's statement trace to pause one connection just before its first INSERT, UPDATE, DELETE or REPLACE, while a second connection runs and commits. It works however the SQL is issued and whatever locking strategy the code uses, and it always releases the paused connection. Scheduling failures are reported as infrastructure errors, never as grading verdicts. Each race test covers one schedule, not every interleaving.

**Mutation audit** (`results/mutation_audit.json`, 32 variants):
- 16 known-good variants are accepted: the unmodified references, a plain deferred `BEGIN` in place of `BEGIN IMMEDIATE`, and an independent conditional-update implementation for T02/T12.
- 12 of 12 candidate race variants are detected. These remove `BEGIN IMMEDIATE`, and in a second version also route SQL through a cursor, on T01, T02 and T10–T13.
- 4 of 4 must-reject variants are rejected: a partially committed journal (T03), balance and inbox committed without the outbox (T10 and T13), and the T14 refund-only fix.

A rejection counts only if it maps to a documented invariant. For race tests, it also counts only when the probe confirms the overlap actually happened, which it did for every race variant. Locally recorded controls are not substitutes for Oracle/NOP inside Harbor. Any prompt/grader modification after seeing model results requires recording a new benchmark version and rerunning comparable models.

## Prior work, sources and use of AI

The project is an original synthetic Python/SQLite evaluation scaffold first developed during the 2026 micro1 hackathon, using general principles of financial transaction correctness. These include idempotency keys, check-then-write races, transactional inbox/outbox and double-entry posting. It does not intentionally incorporate private client or employer code or licensed proprietary datasets. The Harbor task layout follows publicly documented Harbor/Terminal-Bench patterns (see `evaluation/REPRODUCIBILITY.md`).

AI coding assistance (Claude Code with Claude Opus 5.5) was used substantially. It drafted and implemented parts of the task scaffolding, reference solutions, wrong-fix mutants, graders, the race probe, the mutation audit, the trial runner, and drafts of this README and `results/RESULTS_REPORT.md`. The evaluated models come from the same model family, which is a potential source of bias in both task design and results. **HUMAN_REVIEW_PENDING:** before final submission, describe your actual independent checks and corrections of every reference implementation, grader assertion and accounting convention. Do not claim review you have not performed.

## Submission readiness and packaging

```bash
python scripts/check_submission.py
# After genuine trials + video + human review + completed README:
python scripts/check_submission.py --strict
python scripts/package_submission.py --out /tmp/transaction-integrity-eval-submission.zip --final
```

Official micro1 format: one ZIP under 50 MB with this README at the ZIP root; a publicly accessible **≤5-minute audio video** linked in the README and form; a short description in both places; the task inputs/expected outcomes and graders; genuine raw model outputs, model IDs, settings, scores, and source/provenance. No videos, secrets, confidential materials or third-party content without rights inside the ZIP. The official deadline shown in the participant instructions is **November 9, 2026, 05:15 GMT**. Only the latest completed submission is evaluated.
