"""Controlled two-connection scheduling for financial invariant grading.

Connection A is paused immediately BEFORE its first data-modifying statement
(INSERT/UPDATE/DELETE/REPLACE, including `WITH ... INSERT` and statements behind
leading SQL comments) via sqlite3's statement trace hook. The hook sits on the
connection itself, so it sees every statement however the code issues it
(conn.execute, conn.cursor().execute, executemany, executescript) and whatever
the SQL text looks like. A check-then-write implementation has finished its
decisive reads at that point, so competing connection B gets a window to commit.

B is given up to WINDOW seconds; then A is always released. A correct solution
that holds a lock (BEGIN IMMEDIATE, or a deferred BEGIN whose earlier read holds
a SHARED lock) simply makes B wait on its busy timeout, or makes one side raise
a lock-timeout OperationalError, so there is no deadlock. Only persisted
outcomes are asserted by the tests, never the locking strategy.

Known limitation: the pause happens at the FIRST write. An implementation that
writes, then performs its decisive read, then writes again is paused before the
first write, not at the decisive read. Such code is still graded on persisted
outcomes, but the probe does not guarantee B commits between that read and the
later write. See docs/GRADER_HARDENING.md.

Scheduling/infrastructure failures raise RaceProbeInfrastructureError (message
prefixed RACE_PROBE_INFRA) so audits never count them as invariant violations.
Set RACE_PROBE_REPORT=<path> to append per-run JSON diagnostics to that file.
"""
import json
import os
import re
import sqlite3
import threading
import time

_LEADING_NOISE = re.compile(r'^(\s+|--[^\n]*(\n|$)|/\*.*?\*/)+', re.DOTALL)
_WRITE = re.compile(r'^(INSERT|UPDATE|DELETE|REPLACE)\b', re.IGNORECASE)
_CTE_WRITE = re.compile(r'^WITH\b.*\b(INSERT|UPDATE|DELETE|REPLACE)\b', re.IGNORECASE | re.DOTALL)

WINDOW = 1.5          # seconds B may run while A is paused
A_START_WAIT = 1.0    # seconds to wait for A to reach its first write
PAUSE_LIMIT = 12.0    # hard cap on any pause (A is released earlier in practice)
JOIN_LIMIT = 10.0     # per-worker join timeout after release
BUSY_TIMEOUT = 5      # sqlite3.connect(timeout=...) for both workers


class RaceProbeInfrastructureError(RuntimeError):
    """The probe could not schedule or observe the workers; not a grading verdict."""

    def __init__(self, message):
        super().__init__('RACE_PROBE_INFRA: ' + message)


class RaceOutcomes(list):
    """[(result, error), (result, error)] plus scheduling diagnostics."""
    diagnostics = None

    @property
    def race_exercised(self):
        """True when B ran on its own connection while A was paused before a write."""
        d = self.diagnostics or {}
        return bool(d.get('a_paused') and d.get('b_started_while_a_paused'))


def is_write(sql):
    text = _LEADING_NOISE.sub('', sql or '')
    return bool(_WRITE.match(text) or _CTE_WRITE.match(text))


def pair_on_file(db_path, invoke_a, invoke_b, read_marker=None):
    """Run A and B on independent connections; return RaceOutcomes.

    read_marker is accepted for backward compatibility and ignored: pausing on
    SQL text let differently-worded or cursor-based code skip the race entirely.
    """
    reached, release, finished_b = threading.Event(), threading.Event(), threading.Event()
    outcomes = RaceOutcomes([None, None])
    diag = dict(a_paused=False, a_pause_statement=None, b_started_while_a_paused=False,
                b_finished_while_a_paused=False, pause_seconds=0.0, release_timed_out=False)

    def trace(stmt):
        if reached.is_set() or not is_write(stmt):
            return
        diag['a_paused'] = True
        diag['a_pause_statement'] = ' '.join(str(stmt).split())[:120]
        started = time.monotonic()
        reached.set()
        if not release.wait(PAUSE_LIMIT):
            diag['release_timed_out'] = True
        diag['pause_seconds'] = round(time.monotonic() - started, 3)

    def a():
        conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT, check_same_thread=False)
        conn.set_trace_callback(trace)
        try:
            outcomes[0] = (invoke_a(conn), None)
        except Exception as ex:
            outcomes[0] = (None, ex)
        finally:
            conn.set_trace_callback(None)
            conn.close()

    def b():
        if reached.is_set() and not release.is_set():
            diag['b_started_while_a_paused'] = True
        conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT, check_same_thread=False)
        try:
            outcomes[1] = (invoke_b(conn), None)
        except Exception as ex:
            outcomes[1] = (None, ex)
        finally:
            conn.close()
            if reached.is_set() and not release.is_set():
                diag['b_finished_while_a_paused'] = True
            finished_b.set()

    ta = threading.Thread(target=a, daemon=True, name='race-probe-A')
    tb = threading.Thread(target=b, daemon=True, name='race-probe-B')
    try:
        ta.start()
        reached.wait(A_START_WAIT)   # A may reject without writing; B still runs
        tb.start()
        finished_b.wait(WINDOW)
    finally:
        release.set()                # A is always released, even on error
    ta.join(timeout=JOIN_LIMIT)
    tb.join(timeout=JOIN_LIMIT)
    outcomes.diagnostics = diag
    _report(diag)
    if ta.is_alive() or tb.is_alive():
        raise RaceProbeInfrastructureError('worker exceeded timeout')
    if diag['release_timed_out']:
        raise RaceProbeInfrastructureError('paused connection was not released in time')
    if any(x is None for x in outcomes):
        raise RaceProbeInfrastructureError('missing worker outcome')
    return outcomes


def _report(diag):
    path = os.environ.get('RACE_PROBE_REPORT')
    if not path:
        return
    try:
        with open(path, 'a') as fh:
            fh.write(json.dumps(diag, sort_keys=True) + '\n')
    except OSError:
        pass


def permissible_error(error):
    if error is None:
        return True
    if isinstance(error, ValueError):
        return True
    return isinstance(error, sqlite3.OperationalError) and any(
        word in str(error).lower() for word in ('locked', 'busy')
    )
