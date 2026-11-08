# Transaction Integrity Eval

**A reproducible coding-agent benchmark of financial transaction integrity.**

147 recorded Claude Code CLI trials across 14 tasks and 3 models. Full results: [`results/RESULTS_REPORT.md`](results/RESULTS_REPORT.md) · Experiment report (PDF): [`results/REPORT.pdf`](results/REPORT.pdf) · Human review: [`results/HUMAN_REVIEW.md`](results/HUMAN_REVIEW.md)

## Short description: domain, gap and key finding

The domain is financial-transaction software engineering. This eval tests whether AI coding agents preserve ledger and payment invariants when requests are retried, overlap, arrive out of order, or fail halfway through. Such defects lead to duplicate charges, excess refunds, missing payouts, or inconsistent account books, and they rarely show up on the happy path.

**Key finding.** I expected the models to fail on concurrency. They didn't. Across 147 trials on Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5, every race test passed. That held even when I removed every mention of races and transactions and only said the service runs on several workers (T11–T13). It also held when a bug report pointed at one write path but three needed fixing (T14). The two failures I did get (2/147, both on T14) were not missing locks. Both came from the model opening the transaction correctly and then leaving it the wrong way: once through an early return, once through an error path. The models knew *to* lock. What they occasionally got wrong was closing the transaction on every exit.

## Video walkthrough link

**VIDEO_URL_PENDING**: replace this line with the public YouTube/Loom/Vimeo/Google Drive link (no login, at most 5 minutes, with audio). Use the same link in the micro1 form.

## Domain expertise and intended audience

The author is a backend software engineer with over 14 years of experience in Python, Ruby on Rails and Node.js, software architecture, debugging and automated regression testing, and has worked on AI coding evaluation tasks. The tasks draw on that background: payment idempotency, relational transaction boundaries, double-entry journals, settlement matching, integer/decimal money arithmetic, sequence-numbered event handling and audit trails.

Intended readers are payments and backend engineers who review AI-written transactional code, and coding-agent researchers who need graders that can actually detect these failures. A failure matters because a plausible implementation can silently corrupt money-related state during a retry or partial write.

## Tasks and scoring

There are **11 distinct problems plus 3 instruction-only ablations** (14 task folders). Each has a precise `instruction.md`, an intentionally flawed `environment/service.py`, a withheld reference solution, a withheld deliberately incorrect mutant, and a withheld pytest grader.

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

Reward **1** means all task assertions pass; **0** means at least one fails. No LLM-as-judge is used. The score reflects the final code's behavior, not the text of the response or a preferred SQL statement. See [`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md) for problem details and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the trust boundary.

## Setup and run instructions

Requires Python 3.11+ and `pytest==9.0.2` (pinned in `requirements.txt`). No API key is needed to validate the benchmark.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# Validate all graders (reference passes; starter and wrong fix fail) — one command, ~10 s, no API key
python run_eval.py validate

# Optional deeper checks (a few minutes, no API key)
python scripts/preflight.py
python scripts/manifest.py --check
python scripts/audit_variants.py
python scripts/repeatability.py --rounds 3
```

### Re-running the model trials

Trials use the [Claude Code CLI](https://docs.claude.com/en/docs/claude-code/overview) in headless mode. Authenticate the CLI with a Claude login, or set `ANTHROPIC_API_KEY` (see `.env.example`; never commit a value).

```bash
# One command reproduces the full experiment (147 trials)
python scripts/run_claude_trials.py --models claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5 \
  --tasks T01,T02,T03,T04,T05,T06,T07,T08,T09,T10,T11,T12,T13 --trials 3 --parallel 2
python scripts/run_claude_trials.py --models claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5 \
  --tasks T14 --trials 10 --parallel 2

# Dry run: prepares workspaces and prints the exact CLI command, no model calls
python scripts/run_claude_trials.py --models claude-haiku-5-5 --tasks T01 --trials 1 --dry-run
```

Each trial runs in a fresh temporary workspace outside the repository containing only `INSTRUCTION.md` and the starter `service.py`. Results, grades, final code and raw transcripts are appended to `results/` and `transcripts/`; interrupted batches resume without overwriting recorded evidence. Infrastructure failures (auth, rate limits, crashes, timeouts) are never recorded as model failures.

**Runtime and cost (measured).** Agent time across all 147 trials was about 76 minutes (4,535 s); with `--parallel 2` the batches ran between 16:57 and 18:56 UTC, including pauses between batches. CLI-reported cost was **$13.24** in total (Opus $9.77, Sonnet $3.15, Haiku $0.32). Costs are API-equivalent figures reported by the CLI and were not checked against billing.

**Note:** the local runner executes agent-generated code without a security sandbox. See [`evaluation/REPRODUCIBILITY.md`](evaluation/REPRODUCIBILITY.md) for isolation limits. Harbor/Docker task manifests are included (`task.toml`, `tests/test.sh`) but Harbor Oracle/NOP runs were **not** performed for this submission.

## Models tested and results

There were 147 recorded trials, with **145 passed**. All of them are reported; none were excluded. The transcript audit flagged **0 of 147** trials for network or answer-key access. All trials ran on 2026-11-08.

| Model (exact ID) | Agent/version | Settings | Tasks | Trials per task | Pass rate | Observed pass@k / pass^k | Runtime | Cost |
|---|---|---|---|---|---|---|---|---|
| `claude-opus-5-5` | Claude Code CLI 2.1.319 | CLI default temperature; max 40 turns; tools Read/Edit/Write/Bash; no web tools or MCP | T01–T14 | 3 (T14: 10) | 48/49 | 1 / 1 on all tasks except T14 (1 / 0) | 2,509 s | $9.77 |
| `claude-sonnet-5-5` | Claude Code CLI 2.1.319 | same | T01–T14 | 3 (T14: 10) | 48/49 | 1 / 1 on all tasks except T14 (1 / 0) | 785 s | $3.15 |
| `claude-haiku-5-5` | Claude Code CLI 2.1.319 | same | T01–T14 | 3 (T14: 10) | 49/49 | 1 / 1 on all tasks | 1,241 s | $0.32 |

| Task group | What the instruction says | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|---|
| T01–T10 (baseline) | Explicit contract, including the concurrency requirement where relevant | 30/30 | 30/30 | 30/30 |
| T11–T13 (ablation of T01/T02/T10) | Same tests; no mention of races, concurrency, transactions or locking, only absolute invariants plus "several worker processes; each call uses its own SQLite connection" | 9/9 | 9/9 | 9/9 |
| T14 refund write paths | Bug report about over-refunds plus the full contract for `refund`, `adjust_capture` and `void_remaining`; all three must be protected | 9/10 | 9/10 | 10/10 |

**Chronology.** (1) T01–T10 baseline; (2) T11–T13 ablation, designed after the baseline passed; (3) T14 with 3 trials per model, designed after the ablation passed; (4) after the first T14 failure, T14 was extended to 10 trials per model. The T14 instruction and grader were identical for all 30 T14 trials. Race tests (in T01, T02 and T10–T14) passed in all 84 trials that contain them.

Raw evidence: [`results/trials.jsonl`](results/trials.jsonl) (per-trial model, settings, runtime, cost and SHA-256 of instruction, grader, code and transcript), [`results/summary.json`](results/summary.json), [`results/grades/`](results/grades/), [`results/final_code/`](results/final_code/), [`transcripts/`](transcripts/), [`results/network_audit.json`](results/network_audit.json).

## Failure analysis and key insight

Both failing solutions put `BEGIN IMMEDIATE` on all three write paths and passed all four T14 race tests. They failed on sequential tests that exercise the less common exits. Full excerpts and grader output: [`results/RESULTS_REPORT.md`](results/RESULTS_REPORT.md).

- **Sonnet 5.5, T14 trial 3: leaked transaction on replay.** In `refund`, the branch that handles an exact replay returns the stored receipt straight out of the `try` block. There is no `commit()` or `rollback()` on that path, and the `except` only runs on errors. The replay itself looks correct, but the connection is left holding an open write transaction. The next call on the same connection fails with `cannot start a transaction within a transaction` instead of the `ValueError` the spec requires. In production this is worse than a wrong exception: the leaked transaction keeps SQLite's write lock, so one retried request on a pooled connection can stall every other worker.

  ```python
  conn.execute('BEGIN IMMEDIATE')
  prior = conn.execute('SELECT ... FROM refunds WHERE refund_key=?', (refund_key,)).fetchone()
  if prior:
      ...
      return {...}          # returns with the write transaction still open
  ```

  Evidence: [transcript](transcripts/T14_claude-sonnet-5-5_claude-code-cli_trial03.jsonl) · [final code](results/final_code/T14_claude-sonnet-5-5_trial03.py)

- **Opus 5.5, T14 trial 8: rollback helper that commits.** Opus wrapped transactions in its own helpers. Its `_rollback` starts by calling `_begin_safe` → `_begin`, and `_begin` "cleans up" by committing any open transaction. So when the refund-receipt `INSERT` failed, the error path committed the balance update that had already run, and then rolled back an empty transaction. The customer ended up credited 200 cents with no refund receipt. That breaks two stated rules: a call that raises must leave the database unchanged, and no credit may exist without its receipt.

  ```python
  def _rollback(conn):
      _begin_safe(conn)     # calls _begin() ...
      ...
      conn.rollback()

  def _begin(conn):
      if conn.in_transaction:
          conn.commit()     # ... which commits the failed transaction's partial write
  ```

  Evidence: [transcript](transcripts/T14_claude-opus-5-5_claude-code-cli_trial08.jsonl) · [final code](results/final_code/T14_claude-opus-5-5_trial08.py)

I checked both against the spec and the code. Neither is a false failure: each maps to an explicit sentence in the instruction and shows up as a wrong exception type or wrong persisted state. On 13 of the 14 tasks, all three models passed every trial.

**Hot take.** Race tests alone would have scored these models perfectly. Locking was never the problem in my runs: no model failed a race test in any of the 84 trials that had one. The bugs that got through were on the exits of a correctly opened transaction, an early return and an error handler, and a race test will never see those. Opus's failure was in the more "defensive" code: an extra safety helper is exactly what turned its rollback into a commit. My takeaway for anyone evaluating or reviewing AI-written transaction code: test every way out of the transaction (replay, conflict, injected failure, and the call that comes after), not just the concurrent path. With two failures this is a hypothesis to test at larger scale, not a measured failure rate.

## Grader reliability

Every task has three controls: the reference must pass, and the starter and the mutant must fail. All 14 tasks pass these controls ([`results/validation.json`](results/validation.json)). `scripts/repeatability.py --rounds 3` reproduces all 63 expected control outcomes on the race tasks.

**Race probe.** T01, T02 and T10–T14 use a race probe (`tests/race_probe.py`). It hooks SQLite's statement trace to pause one connection just before its first INSERT, UPDATE, DELETE or REPLACE, while a second connection runs and commits. It works however the SQL is issued and whatever locking strategy the code uses, and it always releases the paused connection. Scheduling failures are reported as infrastructure errors, never as grading verdicts. Each race test covers one schedule, not every interleaving.

The first version of the probe paused by matching SQL text on `conn.execute`. Testing it against deliberately broken copies of our own references showed it passed cursor-style code without a transaction on T01, T02 and T10 (on T02, 1,400 cents refunded against a 1,000-cent capture) and paused too early on T10. It was replaced before any model trial.

**Mutation audit** ([`results/mutation_audit.json`](results/mutation_audit.json), 32 variants):
- 16 known-good variants are accepted: the unmodified references, a plain deferred `BEGIN` in place of `BEGIN IMMEDIATE`, and an independent conditional-update implementation for T02/T12.
- 12 of 12 candidate race variants are detected. These remove `BEGIN IMMEDIATE`, and in a second version also route SQL through a cursor, on T01, T02 and T10–T13.
- 4 of 4 must-reject variants are rejected: a partially committed journal (T03), balance and inbox committed without the outbox (T10 and T13), and the T14 refund-only fix.

A rejection counts only if it maps to a documented invariant. For race tests, it also counts only when the probe confirms the overlap actually happened, which it did for every race variant.

## Limitations

- **Small sample.** Two failures in 147 trials; the 9/10 versus 10/10 differences on T14 are not a model ranking.
- **Bounded scheduling.** Each race test exercises one interleaving; code that writes, reads, then writes again may not be paused at its decisive read.
- **Isolation.** No network or filesystem sandbox: the agent's Bash tool could reach the network. The transcript audit is a screen, not proof. Trials ran without `--bare`, so user-level Claude Code settings could load.
- **Post-hoc extensions.** T11–T13 and T14 were designed after earlier results, and T14 was extended after its first failure. All trials are reported.
- **One model family, one agent, SQLite only.** Harbor/Docker execution was not run; SQLite locking differs from PostgreSQL.

## Prior work, sources and use of AI

The project is an original synthetic Python/SQLite evaluation built during the 2026 micro1 hackathon (first commit 2026-10-31), using general principles of financial transaction correctness: idempotency keys, check-then-write races, transactional inbox/outbox and double-entry posting. No existing benchmark or dataset is used, and no private client or employer code is included. The Harbor task layout follows publicly documented Harbor/Terminal-Bench conventions.

**Use of AI.** AI assistance (Claude, via Claude Code and chat) was used substantially. It drafted and implemented parts of the task scaffolding, reference solutions, wrong-fix mutants, graders, the race probe, the mutation audit, the trial runner, and drafts of this README, `results/RESULTS_REPORT.md` and `results/REPORT.pdf`. The evaluated models come from the same model family, which is a potential source of bias in both task design and results.

**What I decided and checked myself** (details in [`results/HUMAN_REVIEW.md`](results/HUMAN_REVIEW.md)): I chose the domain and the hypothesis; reviewed the race-probe loopholes and the evidence for the fix before accepting it; decided that plain `BEGIN` is a valid solution rather than a mutant; approved every spec clarification and the T11–T14 instructions behavior by behavior; ran every trial batch; decided to add T11–T13 and T14 and to extend T14 after its first failure; and read both failing implementations to identify each root cause.

## Packaging

```bash
python scripts/check_submission.py --strict
python scripts/package_submission.py --out /tmp/transaction-integrity-eval-submission.zip --final
```
