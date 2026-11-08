# Human Review Notes — Transaction Integrity Eval

**Experiment:** Transaction Integrity Eval · micro1 Eval Hackathon 2026  
**Author:** El-Moatasem Madani  
**Review date:** 8 November 2026  
**Scope:** 14 Python/SQLite tasks; grader controls; 147 Claude Code CLI trials  
**Repository:** https://github.com/El-Moatasem/transaction-integrity-eval

## Executive finding

Across **147 recorded trials**, three Claude models passed **145**. Every concurrency race test passed, including on tasks where the instructions did not explicitly mention transactions or locking. The two observed failures were both in **T14 (Refund Write Paths)**, and both involved **leaving a correctly opened transaction incorrectly**:

- **Sonnet 5.5, trial 3:** an idempotent refund replay returned from inside `BEGIN IMMEDIATE` without closing the transaction, retaining a write lock.
- **Opus 5.5, trial 8:** a rollback helper called another helper that committed the failed transaction, leaving a **200-cent balance credit without a refund receipt**.

T14 began with three attempts per model and was extended to ten after the first failure. All attempts were included in the results. **The practical conclusion:** the tested models generally protected the concurrent writes, but two generated implementations failed to cleanly exit a transaction on a less common path.

## 1. The original race-harness loopholes

The first race probe paused connection A by wrapping `conn.execute` and matching particular SQL strings. An AI-assisted audit and subsequent mutation tests exposed two false-pass mechanisms.

**Cursor bypass.** When deliberately broken T01, T02 and T10 implementations issued their SQL through `conn.cursor().execute(...)`, the wrapper did not see the statements. The original tests passed those transaction-free variants. In the T02 reproduction, **1,400 cents** of refunds committed against a **1,000-cent** capture.

**Wrong pause point in T10.** The original probe paused after the inbox lookup but before the account-balance read. The competing write could become visible before A made its decision. A transaction-free T10 implementation passed **five out of five** runs under that schedule.

**Correction.** The probe now uses SQLite's `set_trace_callback` on the connection and pauses A immediately before its first modifying statement (`INSERT`, `UPDATE`, `DELETE` or `REPLACE`). It observes cursor-issued SQL as well as connection-issued SQL, releases paused workers on errors, and reports scheduling failures separately from legitimate assertion failures. The mutation audit checks that the intended concurrency window was exercised before crediting a mutant rejection.

The first-write pause is not exhaustive: a write–read–write implementation may have its decisive race window *after* that first write. This is the main remaining scheduler limitation.

## 2. Plain `BEGIN` is not an incorrect fix

An early audit treated replacement of `BEGIN IMMEDIATE` with deferred `BEGIN` as a broken solution. I rejected that interpretation. A deferred transaction still groups the read and write operations. Under contention, SQLite may refuse one writer with `sqlite3.OperationalError` (`database is locked`), which the task contract allows if no partial changes persist.

The grader must therefore test **observable committed state**, not require a preferred lock statement. The positive controls include valid plain-`BEGIN` implementations and a conditional-update refund implementation. The negative concurrency variants remove transaction protection entirely; their reads can make independent decisions before a later write commits.

## 3. Specification-to-grader corrections

Before the first model trial, the instructions were updated to describe behaviors already required by the tests. No test assertion or reference solution was changed for these corrections.

| Task | Clarification | Reason |
|---|---|---|
| T01 | A concurrent identical capture returns the original receipt, or a genuine lock-timeout `OperationalError`; it must not leak `IntegrityError`. | The idempotency rule must cover concurrent replay. |
| T01, T02, T03, T10 | Unexpected SQLite write errors roll back all changes and propagate as SQLite exceptions, not `ValueError`. | Injected-failure tests require `sqlite3.DatabaseError` or a subclass. |
| T02 | `capture_id` and `refund_key` must be nonempty strings. | Empty identifiers were already rejected by the grader. |
| T04 | `sequence` must be a positive integer; Boolean values are invalid. | Python treats `True` as an integer unless checked explicitly. |

This review distinguished a specified invalid-input `ValueError` from an unexpected SQLite failure, which must not be disguised as input validation.

## 4. Why T11–T13 were added

The initial T01–T10 experiment produced **90/90 passes** across Opus, Sonnet and Haiku. Its concurrency instructions were unusually explicit: some described competing connections and the need for a transaction. That could allow an agent to follow a supplied recipe rather than infer the production risk.

I added three **instruction-only ablations** after reviewing those results: T11 (capture), T12 (refund ceiling), and T13 (inbox/outbox). Their behavioral requirements, test suites and control implementations stayed the same. Explicit references to races, locks and transactions were removed. The deployment context instead said that the service runs on several worker processes and each call has its own SQLite connection.

The models passed **27/27** ablation trials. The saved implementations show that they still selected atomic approaches: for example, the [T11 Opus trial 1 code](final_code/T11_claude-opus-5-5_trial01.py) uses `BEGIN IMMEDIATE` and a savepoint branch; [T12 Haiku trial 1](final_code/T12_claude-haiku-5-5_trial01.py) locks before checking the refund ceiling; and [T13 Sonnet trial 1](final_code/T13_claude-sonnet-5-5_trial01.py) wraps the inbox/balance/outbox update in a write transaction.

These ablations were **designed after the baseline results**, so I report them as an exploratory follow-up, not as part of a preregistered baseline.

## 5. T14: a shared invariant across three write paths

T14 changes the problem from one refund function to three interacting writers: `refund`, `adjust_capture`, and `void_remaining`. The service must not commit refunds above a capture's current amount, and it must not commit a refund after the capture is voided. The task's concurrency tests exercise refund-versus-adjustment and refund-versus-void in both pause orderings. Sequential tests cover replay, conflicts and database-write failures.

The instruction describes all required behaviors and the multi-worker deployment setting, but does not prescribe a locking method. The deliberately wrong "refund-only" fix is rejected because protecting one function does not protect the shared invariant against the other writers.

| Model | T14 pass count | Failed attempt |
|---|---:|---|
| `claude-opus-5-5` | **9/10** | Trial 8 — rollback helper commits a partial write |
| `claude-sonnet-5-5` | **9/10** | Trial 3 — replay leaves an open write transaction |
| `claude-haiku-5-5` | **10/10** | None |
| **Total** | **28/30** | **2 failures** |

### Sonnet, T14 trial 3 — transaction leaked on replay

The implementation opened `BEGIN IMMEDIATE` and handled an exact refund-key replay by returning the previously recorded receipt directly from the `try` block. That path did not commit or roll back. The next operation on the same connection raised **`sqlite3.OperationalError: cannot start a transaction within a transaction`** rather than the expected validation exception. An open SQLite write transaction can also block other workers.

Simplified code path, not a verbatim excerpt:

```python
conn.execute('BEGIN IMMEDIATE')
prior = conn.execute('SELECT ... FROM refunds WHERE refund_key=?', (refund_key,)).fetchone()
if prior:
    return existing_receipt  # transaction remains open
```

Evidence paths: [`final_code/T14_claude-sonnet-5-5_trial03.py`](final_code/T14_claude-sonnet-5-5_trial03.py), corresponding file in [`grades/`](grades/), and the raw record in [`../transcripts/`](../transcripts/).

### Opus, T14 trial 8 — rollback helper commits

This implementation attempted to centralize transaction handling. Its `_rollback` path first called `_begin_safe`, which reached `_begin`; `_begin` committed an already-active transaction as a form of cleanup. When a database trigger made the refund-receipt insert fail, that helper committed the earlier balance credit before the nominal rollback. The observed persisted difference was **200 cents credited instead of zero, with no refund receipt**.

Simplified call chain, not a verbatim excerpt:

```python
def _begin(conn):
    if conn.in_transaction:
        conn.commit()  # commits the partial write
    conn.execute('BEGIN IMMEDIATE')

def _rollback(conn):
    _begin_safe(conn)  # reaches _begin()
    conn.rollback()
```

Evidence paths: [`final_code/T14_claude-opus-5-5_trial08.py`](final_code/T14_claude-opus-5-5_trial08.py), corresponding file in [`grades/`](grades/), and the raw record in [`../transcripts/`](../transcripts/).

Both failures came from **sequential exit-path tests**. The two models passed the T14 race tests; failure occurred on replay cleanup or injected-write rollback. This distinction is important because simply adding more race scheduling would not directly exercise these defects.

## 6. Recorded model results and grader controls

| Model | T01–T10 | T11–T13 | T14 | Overall |
|---|---:|---:|---:|---:|
| `claude-opus-5-5` | 30/30 | 9/9 | 9/10 | **48/49** |
| `claude-sonnet-5-5` | 30/30 | 9/9 | 9/10 | **48/49** |
| `claude-haiku-5-5` | 30/30 | 9/9 | 10/10 | **49/49** |
| **Combined** | **90/90** | **27/27** | **28/30** | **145/147** |

The experiment report records **84 trials containing race tests**, comprising **174 race-test executions; all passed**. The final grader-control summary reports **16/16 valid implementations accepted, 12/12 broken concurrency variants detected, and 4/4 other must-reject variants rejected**. The transcript screening reported **0/147 flagged** for its selected network and answer-file indicators.

The model runs used **Claude Code CLI 2.1.319**, headless, with `Read`, `Edit`, `Write`, and `Bash`, a 40-turn limit, and the CLI's default temperature. The total CLI-reported model cost was approximately **$13.24**; this is not independently reconciled to provider billing. Per-trial model IDs, settings, time, cost, final-code hashes, grade reports, and transcript hashes are recorded in [`trials.jsonl`](trials.jsonl), [`summary.json`](summary.json), [`grades/`](grades/), and [`../transcripts/`](../transcripts/).

## 7. What I reviewed

- I examined the old race-probe bypasses and the regression evidence that motivated the SQLite trace-callback fix.
- I checked the accepted deferred-`BEGIN` implementation against the contract's lock-timeout rule, rather than treating lock syntax as a correctness requirement.
- I reviewed the instruction changes and the T11–T13/T14 task design against the stated behavioral invariants.
- I ran the reported trial batches and reviewed the model-level and task-level outcomes, retaining both failed T14 attempts in the denominator.
- I inspected the two failing T14 implementations and compared their control flow with the observed grader failures: Sonnet's early return and Opus's commit-before-rollback call chain.

**Practical conclusion.** A race-only grader would have awarded full marks in this experiment. Financial transaction reviews should cover **every exit from a write transaction**: successful write, exact replay, conflicting replay, injected database error, and the next request on the same connection. The Opus failure also shows how an additional "safety" helper can turn an intended rollback into a commit.

## 8. Boundaries and AI-use disclosure

These are 147 attempts on one SQLite benchmark using one agent interface and three Claude models; T11–T14 were added after earlier results, and T14 was expanded after observing a failure. Race coverage uses selected SQLite schedules rather than exhaustive interleavings. Bash could access the local filesystem and network during the runs; transcript screening is not full isolation. This experiment is **local Claude Code evaluation, not a claimed Harbor/Docker run**.

**AI use:** Claude Code and chat assistance contributed to task design, implementations, graders, runner instrumentation, debugging, analysis, and drafting this report. I directed the experiment and remain responsible for reviewing the evidence and claims included in the submission.
