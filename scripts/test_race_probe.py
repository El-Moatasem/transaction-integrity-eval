#!/usr/bin/env python3
"""Self-tests for tasks/*/tests/race_probe.py (the shared concurrency scheduler).

Run: python -m unittest discover -s scripts -p 'test_race_probe.py'
These exercise the probe on a toy debit schema; they do not explore every
SQLite interleaving.
"""
import importlib.util
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPIES = [ROOT / 'tasks' / t / 'tests' / 'race_probe.py' for t in
          ('T01_capture-idempotency', 'T02_refund-ceiling', 'T10_inbox-outbox-atomicity')]

spec = importlib.util.spec_from_file_location('race_probe_under_test', COPIES[0])
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def seed(path):
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE accounts(id TEXT PRIMARY KEY, balance INTEGER NOT NULL)')
        c.execute('CREATE TABLE ledger(entry TEXT PRIMARY KEY, id TEXT, delta INTEGER)')
        c.execute("INSERT INTO accounts VALUES('a', 100)")
    c.close()


def state(path):
    with sqlite3.connect(path) as c:
        bal = c.execute("SELECT balance FROM accounts WHERE id='a'").fetchone()[0]
        n = c.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]
    c.close()
    return bal, n


# --- implementations under test ------------------------------------------------

def unsafe_insert_first(entry):
    """Check-then-write, autocommit-style, first write is INSERT."""
    def run(conn):
        bal = conn.execute("SELECT balance FROM accounts WHERE id='a'").fetchone()[0]
        if bal < 70:
            raise ValueError('insufficient')
        conn.execute('INSERT INTO ledger VALUES(?,?,?)', (entry, 'a', -70))
        conn.execute("UPDATE accounts SET balance=? WHERE id='a'", (bal - 70,))
        conn.commit()
        return bal - 70
    return run


def unsafe_update_first_cursor(entry):
    """Check-then-write via conn.cursor().execute(); first write is UPDATE."""
    def run(conn):
        cur = conn.cursor()
        bal = cur.execute("SELECT balance FROM accounts WHERE id='a'").fetchone()[0]
        if bal < 70:
            raise ValueError('insufficient')
        cur.execute("/* debit */ UPDATE accounts SET balance=? WHERE id='a'", (bal - 70,))
        cur.execute('INSERT INTO ledger VALUES(?,?,?)', (entry, 'a', -70))
        conn.commit()
        return bal - 70
    return run


def locked(begin, entry):
    def run(conn):
        try:
            conn.execute(begin)
            bal = conn.execute("SELECT balance FROM accounts WHERE id='a'").fetchone()[0]
            if bal < 70:
                raise ValueError('insufficient')
            conn.execute("UPDATE accounts SET balance=? WHERE id='a'", (bal - 70,))
            conn.execute('INSERT INTO ledger VALUES(?,?,?)', (entry, 'a', -70))
            conn.commit()
            return bal - 70
        except BaseException:
            conn.rollback()
            raise
    return run


def conditional_update(entry):
    def run(conn):
        try:
            conn.execute('BEGIN')
            cur = conn.execute("UPDATE accounts SET balance=balance-70 WHERE id='a' AND balance>=70")
            if cur.rowcount != 1:
                raise ValueError('insufficient')
            conn.execute('INSERT INTO ledger VALUES(?,?,?)', (entry, 'a', -70))
            conn.commit()
            return 'ok'
        except BaseException:
            conn.rollback()
            raise
    return run


class RaceProbeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='race-probe-test-')
        self.db = Path(self._tmp.name) / 't.db'
        seed(self.db)
        self.threads_before = set(threading.enumerate())

    def tearDown(self):
        leaked = [t for t in threading.enumerate()
                  if t not in self.threads_before and t.name.startswith('race-probe')]
        self.assertEqual(leaked, [], 'probe left worker threads running')
        self._tmp.cleanup()

    def test_copies_identical(self):
        texts = {p.read_text() for p in COPIES}
        self.assertEqual(len(texts), 1, 'T01/T02/T10 race_probe.py copies diverged')

    def test_write_detection(self):
        for sql in ('INSERT INTO t VALUES(1)', '  update t set x=1', 'DELETE FROM t',
                    'REPLACE INTO t VALUES(1)', 'insert or replace into t values(1)',
                    '-- note\nUPDATE t SET x=1', '/* c */ DELETE FROM t',
                    'WITH s AS (SELECT 1) INSERT INTO t SELECT * FROM s'):
            self.assertTrue(probe.is_write(sql), sql)
        for sql in ('SELECT * FROM t', 'BEGIN IMMEDIATE', 'COMMIT', '', None,
                    "SELECT 'INSERT' FROM t", 'WITH s AS (SELECT 1) SELECT * FROM s'):
            self.assertFalse(probe.is_write(sql), sql)

    def test_insert_interception_exposes_lost_update(self):
        out = probe.pair_on_file(self.db, unsafe_insert_first('A'), unsafe_insert_first('B'))
        d = out.diagnostics
        self.assertTrue(out.race_exercised, d)
        self.assertTrue(d['a_pause_statement'].upper().startswith('INSERT'), d)
        self.assertTrue(d['b_finished_while_a_paused'], d)
        self.assertEqual([e for _, e in out], [None, None])
        self.assertEqual(state(self.db), (30, 2), 'lost update should be visible to the grader')

    def test_cursor_update_interception_exposes_lost_update(self):
        out = probe.pair_on_file(self.db, unsafe_update_first_cursor('A'), unsafe_update_first_cursor('B'))
        d = out.diagnostics
        self.assertTrue(out.race_exercised, d)
        self.assertIn('UPDATE', d['a_pause_statement'].upper())
        self.assertTrue(d['b_finished_while_a_paused'], d)
        self.assertEqual(state(self.db), (30, 2))

    def test_valid_locking_strategies_accepted(self):
        for name, factory in (('BEGIN IMMEDIATE', lambda e: locked('BEGIN IMMEDIATE', e)),
                              ('BEGIN', lambda e: locked('BEGIN', e)),
                              ('conditional UPDATE', conditional_update)):
            with self.subTest(name):
                self.tearDown(); self.setUp()
                out = probe.pair_on_file(self.db, factory('A'), factory('B'))
                self.assertTrue(out.race_exercised, out.diagnostics)
                for _, err in out:
                    self.assertTrue(probe.permissible_error(err), repr(err))
                bal, n = state(self.db)
                self.assertGreaterEqual(bal, 0)
                self.assertEqual(bal, 100 - 70 * n)
                self.assertLessEqual(n, 1)

    def test_release_after_b_error(self):
        def b_fails(conn):
            raise RuntimeError('boom in B')
        out = probe.pair_on_file(self.db, locked('BEGIN IMMEDIATE', 'A'), b_fails)
        self.assertTrue(out.diagnostics['a_paused'])
        self.assertFalse(out.diagnostics['release_timed_out'])
        self.assertLess(out.diagnostics['pause_seconds'], probe.WINDOW + 1)
        self.assertIsNone(out[0][1])
        self.assertIsInstance(out[1][1], RuntimeError)
        self.assertEqual(state(self.db), (30, 1))

    def test_release_after_a_error_mid_transaction(self):
        def a_fails_after_write(conn):
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("UPDATE accounts SET balance=0 WHERE id='a'")
            raise RuntimeError('boom in A')  # connection close rolls back
        out = probe.pair_on_file(self.db, a_fails_after_write, locked('BEGIN IMMEDIATE', 'B'))
        self.assertIsInstance(out[0][1], RuntimeError)
        self.assertIsNone(out[1][1], repr(out[1][1]))
        self.assertEqual(state(self.db), (30, 1))

    def test_a_without_writes_still_runs_b(self):
        out = probe.pair_on_file(self.db, lambda c: c.execute('SELECT 1').fetchone()[0],
                                 locked('BEGIN IMMEDIATE', 'B'))
        self.assertFalse(out.diagnostics['a_paused'])
        self.assertFalse(out.race_exercised)
        self.assertEqual(state(self.db), (30, 1))

    def test_infrastructure_error_is_distinct(self):
        err = probe.RaceProbeInfrastructureError('x')
        self.assertIn('RACE_PROBE_INFRA', str(err))
        self.assertNotIsInstance(err, AssertionError)
        self.assertFalse(probe.permissible_error(err))


if __name__ == '__main__':
    unittest.main()
