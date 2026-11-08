"""Controlled two-connection scheduling for financial invariant grading.

This intentionally checks persisted state, not a particular SQL lock strategy.
A correct solution that uses BEGIN IMMEDIATE may block B; we always release A
before waiting for a blocked B, preventing test-induced deadlocks.
"""
import sqlite3
import threading


class PauseAfterQuery:
    def __init__(self, inner, marker, reached, resume):
        self._inner = inner
        self._marker = marker
        self._reached = reached
        self._resume = resume
        self.paused_in_transaction = None
        self._paused = False

    def execute(self, sql, params=()):
        cur = self._inner.execute(sql, params)
        norm = ' '.join(str(sql).lower().split())
        if not self._paused and self._marker(norm):
            self._paused = True
            # sqlite3.in_transaction distinguishes held transactions for
            # scheduling. It is NEVER a pass/fail assertion on user code.
            self.paused_in_transaction = self._inner.in_transaction
            if hasattr(self, '_on_pause'):
                self._on_pause(self.paused_in_transaction)
            self._reached.set()
            if not self._resume.wait(12):
                raise RuntimeError('test scheduling failed to release paused read')
        return cur

    def __enter__(self):
        # Keep the instrumentation proxy when evaluated code uses `with conn:`.
        # A sqlite3.Connection context manager normally returns the connection.
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._inner.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name):
        # Forward alternative valid SQLite methods (cursor, executescript, ...).
        return getattr(self._inner, name)


def pair_on_file(db_path, invoke_a, invoke_b, read_marker):
    """Run two operations and return [(result, error), ...] with bounded threads.

    If A executes a relevant SELECT without a transaction, give B a chance to
    commit while A is paused. If A holds a transaction, release A before waiting
    for B. Implementations that use atomic SQL without this read still run.
    """
    reached, release = threading.Event(), threading.Event()
    begun_b, finished_b = threading.Event(), threading.Event()
    outcomes = [None, None]

    def a():
        conn = sqlite3.connect(db_path, timeout=5)
        wrapper = PauseAfterQuery(conn, read_marker, reached, release)
        # publish transaction status at pause time through a tiny adapter
        wrapper._on_pause = lambda held: setattr(ta, '_held_sql_transaction', held)
        try:
            outcomes[0] = (invoke_a(wrapper), None)
        except Exception as ex:
            outcomes[0] = (None, ex)
        finally:
            conn.close()

    def b():
        conn = sqlite3.connect(db_path, timeout=5)
        begun_b.set()
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
    # A may not use a SELECT, which is fine; it still must obey the invariant.
    paused = reached.wait(0.8)
    tb.start()
    try:
        assert begun_b.wait(2), 'competing connection did not start'
        if paused:
            # A SQL transaction can legitimately block B. Never wait for it
            # while A holds a lock. A no-transaction read allows B to commit.
            if not _a_has_open_transaction(ta, reached):
                finished_b.wait(2.0)  # permissive timeout; not a grading assertion
        # Always unblock before joining or observing B's status.
    finally:
        release.set()
    ta.join(timeout=10)
    tb.join(timeout=10)
    assert not ta.is_alive() and not tb.is_alive(), 'worker exceeded timeout'
    assert all(x is not None for x in outcomes), 'missing worker outcome'
    return outcomes


def _a_has_open_transaction(thread, reached):
    # Internal coordination is installed below by closure in pair_on_file.
    return getattr(thread, '_held_sql_transaction', False)


def permissible_error(error):
    if error is None:
        return True
    if isinstance(error, ValueError):
        return True
    return isinstance(error, sqlite3.OperationalError) and any(
        word in str(error).lower() for word in ('locked', 'busy')
    )
