# Results report

All numbers below are computed from `results/trials.jsonl` (147 rows), `results/summary.json`, the per-trial grade reports in `results/grades/` and `results/network_audit.json`. Every recorded trial is reported; none were excluded.

## Totals

| | |
|---|---|
| Trials recorded | **147** |
| Models | 3: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` (49 trials each) |
| Passed | **145 / 147** |
| Failed | 2 (both on T14: Sonnet trial 3, Opus trial 8) |
| Race tests | All passed in every trial that contains them: 84 trials (T01, T02, T10, T11, T12, T13, T14), 174 race-test executions, 0 failures. T03–T09 have no race tests. |
| Network/answer-key transcript audit | **0 / 147** trials flagged |
| Turn budget exhausted | 0 / 147 |
| Incomplete (ungradable) attempts | 0 |
| Total cost reported by the CLI | $13.24 (Opus $9.77, Sonnet $3.15, Haiku $0.32) |

## Frozen setup

- **Agent:** Claude Code CLI `2.1.319`, driven by `scripts/run_claude_trials.py` (agent ID `claude-code-cli`) in non-interactive mode (`claude -p`).
- **Prompt (identical for every trial):** "Your task is described in INSTRUCTION.md in the current directory. Read it, then implement the required changes in service.py. Work only inside the current directory. When you are finished, stop."
- **Settings:**
  - `--max-turns 40`
  - `--permission-mode acceptEdits`
  - allowed tools `Read,Edit,Write,Bash`
  - disallowed tools `WebFetch,WebSearch`
  - `--strict-mcp-config` (no MCP servers)
  - temperature: CLI default (not configurable)
  - `--bare` not used
- **Workspace:** each trial ran in a fresh temporary directory outside the repository, containing only `INSTRUCTION.md` and the starter `service.py`.
- **Grading:** the final `service.py` was graded by the withheld pytest grader (`run_eval.py grade`). The reward is binary: every test must pass.
- **Recorded per trial:** requested and reported model (they match in all 147 trials), transcript, final code, grade report, and the SHA-256 of the instruction, grader, code and transcript.
- **Dates:** all trials ran on 2026-11-08 between 16:57 and 18:56 UTC.

## Chronology

1. **Baseline, T01–T10** (16:57–17:51 UTC): 3 models × 10 tasks × 3 trials = 90 trials. Each instruction states the concurrency requirement explicitly ("Independent SQLite connections may…").
2. **Ablation, T11–T13** (17:52–17:59 UTC): 3 models × 3 tasks × 3 trials = 27 trials. These are copies of T01, T02 and T10 with identical tests, references and wrong fixes. Their instructions drop every mention of races, concurrency, transactions and locking, and instead state absolute invariants plus the fact "This service runs on several worker processes; each call uses its own SQLite connection."
3. **T14 refund write paths, trials 1–3** (18:37–18:42 UTC): 9 trials. The instruction is a bug report ("customers were refunded more than was captured") followed by the full contract for three functions (`refund`, `adjust_capture` and `void_remaining`). All three must be protected, but the report only mentions refunds. The first failure, Sonnet trial 3, was recorded at 18:41:05.
4. **T14 extension to 10 trials per model** (18:46–18:56 UTC): 21 trials (trials 4–10 for each model), added after that first failure. Opus trial 8 failed at 18:50:01.

All 30 T14 trials used the same instruction (SHA-256 prefix `3e747a3a77bd`) and grader (`41031d51fa2a`).

## Per-model × per-task results (passed / trials)

| Task | Instruction style | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|---|
| T01 capture idempotency | explicit | 3/3 | 3/3 | 3/3 |
| T02 refund ceiling | explicit | 3/3 | 3/3 | 3/3 |
| T03 double-entry transfer | explicit | 3/3 | 3/3 | 3/3 |
| T04 webhook ordering | explicit | 3/3 | 3/3 | 3/3 |
| T05 settlement reconciliation | explicit | 3/3 | 3/3 | 3/3 |
| T06 FX rounding | explicit | 3/3 | 3/3 | 3/3 |
| T07 subscription proration | explicit | 3/3 | 3/3 | 3/3 |
| T08 marketplace splits | explicit | 3/3 | 3/3 | 3/3 |
| T09 dispute deadlines | explicit | 3/3 | 3/3 | 3/3 |
| T10 inbox/outbox | explicit | 3/3 | 3/3 | 3/3 |
| T11 capture idempotency | implicit | 3/3 | 3/3 | 3/3 |
| T12 refund ceiling | implicit | 3/3 | 3/3 | 3/3 |
| T13 inbox/outbox | implicit | 3/3 | 3/3 | 3/3 |
| T14 refund write paths | bug report, 3 write paths | **9/10** | **9/10** | 10/10 |
| **Total** | | **48/49** | **48/49** | **49/49** |
| Runtime (sum) | | 2,509 s | 785 s | 1,241 s |
| Cost (CLI-reported) | | $9.77 | $3.15 | $0.32 |

Observed pass@k equals 1 for every model/task group. Observed pass^k equals 1 everywhere except T14 for Opus and for Sonnet, where it is 0.

## The two failures

Both failures are on T14, and both are in sequential (single-connection) tests. Both failing solutions passed all four T14 race tests. In both, `BEGIN IMMEDIATE` was applied to all three write paths. The defect is in how each transaction is closed, not in whether one is opened.

### Sonnet 5.5, T14 trial 3: the replay branch returns inside an open transaction

**Files:**
- `transcripts/T14_claude-sonnet-5-5_claude-code-cli_trial03.jsonl`
- `results/final_code/T14_claude-sonnet-5-5_trial03.py` (code SHA-256 `56eb3891…`, matching the trial record)
- `results/grades/T14_claude-sonnet-5-5_claude-code-cli_trial03.json`

```python
 18    try:
 19        conn.execute('BEGIN IMMEDIATE')
 20        prior=conn.execute('SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',(refund_key,)).fetchone()
 21        if prior:
 22            if prior[0]!=capture_id or prior[1]!=amount_cents:raise ValueError('idempotency conflict')
 23            return {'receipt_id':prior[2],'capture_id':prior[0],'amount_cents':prior[1],'status':'refunded'}
 ...
 34    except BaseException:
 35        conn.rollback();raise
```

An exact replay returns at line 23 without committing or rolling back. The `BEGIN IMMEDIATE` transaction stays open, and with it the connection's write lock. The replay itself returns the correct receipt. The next call on the same connection then fails when it tries to open its own transaction.

**What the grader recorded** (2 failed, 7 passed):

```
FAILED tests/test_service.py::test_refund_ceiling_replay_and_conflicts
>       with pytest.raises(ValueError): refund(c, 'c1', 'r1', 500)
>           conn.execute('BEGIN IMMEDIATE')
E           sqlite3.OperationalError: cannot start a transaction within a transaction

FAILED tests/test_service.py::test_void_remaining_rules
>       with pytest.raises(ValueError): adjust_capture(c, 'c1', 500)
>           conn.execute('BEGIN IMMEDIATE')
E           sqlite3.OperationalError: cannot start a transaction within a transaction
```

**Why the instruction justifies the rejection:**
- A conflicting refund key and an adjustment of a voided capture must raise `ValueError`.
- `sqlite3.OperationalError` is allowed only "if the database is busy".

On a shared connection, the leaked write lock would also block every other worker's writes until something else ends the transaction. This consequence follows from the code; the grader does not test it directly.

### Opus 5.5, T14 trial 8: the rollback helper commits first

**Files:**
- `transcripts/T14_claude-opus-5-5_claude-code-cli_trial08.jsonl`
- `results/final_code/T14_claude-opus-5-5_trial08.py` (code SHA-256 `23b7a238…`, matching the trial record)
- `results/grades/T14_claude-opus-5-5_claude-code-cli_trial08.json`

```python
  7 def _begin(conn):
 ...
 10     if conn.in_transaction:
 11         conn.commit()
 ...
 20         conn.execute('BEGIN IMMEDIATE')
 ...
 39 def _rollback(conn):
 40     _begin_safe(conn)          # -> _begin(conn): commits the in-flight transaction
 41     try:
 ...
 46             conn.rollback()     # now rolls back an empty transaction
 ...
 77         updated=conn.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',(amount_cents,account))
 ...
 79         conn.execute('INSERT INTO refunds VALUES(?,?,?,?)',(refund_key,capture_id,amount_cents,'ref_'+refund_key))
 ...
 82     except BaseException:
 83         _rollback(conn);raise
```

What happens:
1. When the receipt `INSERT` (line 79) fails, the exception handler calls `_rollback`.
2. `_rollback` first calls `_begin_safe`, which calls `_begin`.
3. `_begin` sees an open transaction and **commits** it (line 11). This persists the balance credit from line 77.
4. `_begin` then opens a fresh transaction, which `_rollback` rolls back. Nothing is left in it to undo.

The database exception still propagates correctly, but the account keeps a $2.00 credit with no refund receipt.

**What the grader recorded** (1 failed, 8 passed):

```
FAILED tests/test_service.py::test_database_errors_propagate_and_roll_back
>       assert state(c) == dict(amount=1000, voided=0, refunded=0, credited=0, count=0)
E         Differing items:
E         {'credited': 200} != {'credited': 0}
```

**Why the instruction justifies the rejection:**
- "A call that raises leaves the database unchanged."
- "Every committed refund receipt corresponds to exactly one credit of its amount to available_cents, and no credit exists without its receipt."
- Unexpected database errors "must leave no changes".

## Grader reliability evidence (pre-trial)

- **Controls on every task:** the reference passes, and the starter and deliberately wrong fix fail (`results/validation.json`). Repeating these controls (`scripts/repeatability.py`) is stable.
- **Mutation audit** (`results/mutation_audit.json`):
  - Independently correct variants are accepted: the references, plain deferred `BEGIN`, and an alternative conditional-update implementation.
  - The race tests reject a removed `BEGIN IMMEDIATE`, both with `conn.execute` and with `conn.cursor().execute`, on T01, T02, T10, T11, T12 and T13, and only when the probe confirms the race actually overlapped.
  - On T14, a fix applied only to `refund()` is rejected. Separate checks showed that leaving any single function unprotected fails both orderings of that function's race pair.
- **The two failures are not false failures.** Each corresponds to a contract sentence quoted above, and each shows up as wrong persisted state or a wrong exception type under the plain sequential tests.

## Limitations

- **Race-test coverage:** the race probe pauses the first connection before its first write. It covers one schedule per test, not all interleavings.
- **No network or filesystem isolation.** The Bash tool could have reached the network or read paths outside the workspace. The transcript audit (0/147 flagged) checks tool inputs for network commands, URLs, the repository path and answer files. It is a review aid, not proof of isolation.
- **Host configuration may have loaded.** Trials ran without `--bare`, so user-level Claude Code configuration on the host machine could have been loaded. It was not recorded per trial.
- **Small samples.** n = 3 per task on T01–T13 and n = 10 on T14. The 9/10 versus 10/10 difference on T14 is one trial; it does not establish an ordering between models.
- **Not run in Harbor.** These are local CLI runs, not Harbor/Docker runs; Harbor Oracle/NOP was not executed.
- **One model family.** All three models are Claude models from one provider. The task scaffolding was also built with Claude-based AI assistance (see the README).
- **Cost and runtime** are the CLI's own `total_cost_usd` and wall-clock figures. They have not been reconciled against provider billing.
