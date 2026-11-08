"""Controlled two-connection scheduling for financial invariant grading.

Connection A is paused immediately BEFORE its first data-modifying statement
(INSERT/UPDATE/DELETE/REPLACE), via sqlite3's statement trace hook. The hook sits
on the connection itself, so it sees every statement however the code issues it
(conn.execute, conn.cursor().execute, executemany, executescript) and whatever
the SQL text looks like. Any check-then-write implementation has finished its
reads at that point, so competing connection B gets a window to commit.

B is given up to WINDOW seconds; then A is always released. A correct solution
that holds a lock simply makes B wait on its busy timeout, so no deadlock.
Only persisted outcomes are asserted by the tests, never the locking strategy.
"""
import re
import sqlite3
import threading

WRITE = re.compile(r'^\s*(INSERT|UPDATE|DELETE|REPLACE)\b', re.IGNORECASE)
WINDOW = 1.5


def pair_on_file(db_path, invoke_a, invoke_b, read_marker=None):
    """Run A and B on independent connections; return [(result, error), (result, error)].

    read_marker is accepted for backward compatibility and ignored: pausing on
    SQL text let differently-worded or cursor-based code skip the race entirely.
    """
    reached, release, finished_b = threading.Event(), threading.Event(), threading.Event()
    outcomes = [None, None]

    def trace(stmt):
        if not reached.is_set() and WRITE.match(stmt or ''):
            reached.set()
            release.wait(12)

    def a():
        conn = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
        conn.set_trace_callback(trace)
        try:
            outcomes[0] = (invoke_a(conn), None)
        except Exception as ex:
            outcomes[0] = (None, ex)
        finally:
            conn.set_trace_callback(None)
            conn.close()

    def b():
        conn = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
        try:
            outcomes[1] = (invoke_b(conn), None)
        except Exception as ex:
            outcomes[1] = (None, ex)
        finally:
            conn.close()
            finished_b.set()

    ta = threading.Thread(target=a, daemon=True)
    tb = threading.Thread(target=b, daemon=True)
    ta.start()
    reached.wait(1.0)   # A may reject without writing; B still runs
    tb.start()
    try:
        finished_b.wait(WINDOW)
    finally:
        release.set()
    ta.join(timeout=10)
    tb.join(timeout=10)
    assert not ta.is_alive() and not tb.is_alive(), 'worker exceeded timeout'
    assert all(x is not None for x in outcomes), 'missing worker outcome'
    return outcomes


def permissible_error(error):
    if error is None:
        return True
    if isinstance(error, ValueError):
        return True
    return isinstance(error, sqlite3.OperationalError) and any(
        word in str(error).lower() for word in ('locked', 'busy')
    )
