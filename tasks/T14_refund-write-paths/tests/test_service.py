import sqlite3, pytest
from service import setup, refund, adjust_capture, void_remaining


def db(tmp_path):
    p = tmp_path / 'refund.db'; c = sqlite3.connect(p, timeout=10); setup(c)
    c.executemany('INSERT INTO captures(capture_id,account_id,amount_cents) VALUES(?,?,?)',
                  [('c1', 'alice', 1000), ('c2', 'alice', 500)])
    c.execute('INSERT INTO balances VALUES(?,?)', ('alice', 0)); c.commit(); return p, c


def state(c, cid='c1'):
    amount, voided = c.execute('SELECT amount_cents,voided FROM captures WHERE capture_id=?', (cid,)).fetchone()
    total = c.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?', (cid,)).fetchone()[0]
    credited = c.execute("SELECT available_cents FROM balances WHERE account_id='alice'").fetchone()[0]
    count = c.execute('SELECT COUNT(*) FROM refunds').fetchone()[0]
    return dict(amount=amount, voided=voided, refunded=total, credited=credited, count=count)


# ---------------------------------------------------------------- sequential

def test_refund_ceiling_replay_and_conflicts(tmp_path):
    _, c = db(tmp_path)
    assert refund(c, 'c1', 'r1', 400) == {'receipt_id': 'ref_r1', 'capture_id': 'c1', 'amount_cents': 400, 'status': 'refunded'}
    assert refund(c, 'c1', 'r1', 400) == {'receipt_id': 'ref_r1', 'capture_id': 'c1', 'amount_cents': 400, 'status': 'refunded'}
    with pytest.raises(ValueError): refund(c, 'c1', 'r1', 500)
    with pytest.raises(ValueError): refund(c, 'c2', 'r1', 400)
    assert refund(c, 'c1', 'r2', 600)['amount_cents'] == 600
    with pytest.raises(ValueError): refund(c, 'c1', 'r3', 1)
    assert state(c) == dict(amount=1000, voided=0, refunded=1000, credited=1000, count=2)


def test_invalid_refunds_leave_no_changes(tmp_path):
    _, c = db(tmp_path)
    for cid, key, amt in [('none', 'x', 2), ('', 'x', 2), ('c1', '', 3), ('c1', 'x', 0), ('c1', 'x', -5),
                          ('c1', 'x', True), ('c1', 'x', 2.0), ('c1', 'x', 1001)]:
        with pytest.raises(ValueError): refund(c, cid, key, amt)
    assert state(c) == dict(amount=1000, voided=0, refunded=0, credited=0, count=0)


def test_adjust_capture_rules(tmp_path):
    _, c = db(tmp_path)
    refund(c, 'c1', 'r1', 400)
    assert adjust_capture(c, 'c1', 600) == {'capture_id': 'c1', 'amount_cents': 600, 'status': 'adjusted'}
    for cid, amt in [('c1', 399), ('c1', 601), ('c1', -1), ('c1', True), ('c1', '500'), ('none', 500), ('', 500)]:
        with pytest.raises(ValueError): adjust_capture(c, cid, amt)
    assert state(c)['amount'] == 600
    with pytest.raises(ValueError): refund(c, 'c1', 'r2', 201)      # ceiling follows the adjusted amount
    assert refund(c, 'c1', 'r2', 200)['amount_cents'] == 200
    assert adjust_capture(c, 'c1', 600)['amount_cents'] == 600      # equal to refunded total is allowed
    assert adjust_capture(c, 'c2', 0)['amount_cents'] == 0
    assert state(c) == dict(amount=600, voided=0, refunded=600, credited=600, count=2)


def test_void_remaining_rules(tmp_path):
    _, c = db(tmp_path)
    refund(c, 'c1', 'r1', 250)
    expected = {'capture_id': 'c1', 'status': 'voided', 'refunded_cents': 250, 'voided_cents': 750}
    assert void_remaining(c, 'c1') == expected
    assert void_remaining(c, 'c1') == expected                       # repeat is a no-op
    with pytest.raises(ValueError): refund(c, 'c1', 'r2', 1)         # no new refund after a void
    assert refund(c, 'c1', 'r1', 250)['receipt_id'] == 'ref_r1'      # exact replay still returns the receipt
    with pytest.raises(ValueError): adjust_capture(c, 'c1', 500)
    for cid in ('none', '', None):
        with pytest.raises(ValueError): void_remaining(c, cid)
    assert state(c) == dict(amount=1000, voided=1, refunded=250, credited=250, count=1)
    assert state(c, 'c2')['voided'] == 0


def test_database_errors_propagate_and_roll_back(tmp_path):
    _, c = db(tmp_path)
    c.execute("CREATE TRIGGER fail_refund BEFORE INSERT ON refunds BEGIN SELECT RAISE(ABORT, 'injected refund failure'); END;")
    c.execute("CREATE TRIGGER fail_capture BEFORE UPDATE ON captures BEGIN SELECT RAISE(ABORT, 'injected capture failure'); END;")
    c.commit()
    with pytest.raises(sqlite3.DatabaseError): refund(c, 'c1', 'failure', 200)
    with pytest.raises(sqlite3.DatabaseError): adjust_capture(c, 'c1', 500)
    with pytest.raises(sqlite3.DatabaseError): void_remaining(c, 'c1')
    assert state(c) == dict(amount=1000, voided=0, refunded=0, credited=0, count=0)


# ---------------------------------------------------------------- write paths under contention
# Each pair is run in BOTH orders: the probe pauses connection A just before its
# first write while B runs on its own connection, so every function must be safe.

from race_probe import pair_on_file, permissible_error


def contended(tmp_path, invoke_a, invoke_b):
    path, seed = db(tmp_path)
    seed.close()
    outcomes = pair_on_file(path, invoke_a, invoke_b)
    for _, err in outcomes:
        assert permissible_error(err), f'unexpected error under contention: {err!r}'
    assert any(err is None for _, err in outcomes), 'neither call completed'
    with sqlite3.connect(path, timeout=5) as conn:
        return outcomes, state(conn)


def check_refund_vs_adjust(r, a, s):
    assert s['refunded'] <= s['amount'], 'committed refunds exceed the current captured amount'
    assert s['credited'] == s['refunded'], 'credited balance diverged from committed refund receipts'
    assert s['refunded'] == (700 if r[1] is None else 0)
    assert s['amount'] == (500 if a[1] is None else 1000)
    if r[1] is None:
        assert r[0] == {'receipt_id': 'ref_rA', 'capture_id': 'c1', 'amount_cents': 700, 'status': 'refunded'}
    if a[1] is None:
        assert a[0] == {'capture_id': 'c1', 'amount_cents': 500, 'status': 'adjusted'}


def check_refund_vs_void(r, v, s):
    assert s['refunded'] <= s['amount'], 'committed refunds exceed the current captured amount'
    assert s['credited'] == s['refunded'], 'credited balance diverged from committed refund receipts'
    assert s['refunded'] == (300 if r[1] is None else 0)
    if v[1] is None:
        assert s['voided'] == 1
        # Whatever the void observed must stay true: no refund may commit after it.
        assert v[0]['refunded_cents'] == s['refunded'], 'a refund committed after the capture was voided'
        assert v[0]['voided_cents'] == s['amount'] - s['refunded']
    else:
        assert s['voided'] == 0


def test_refund_paused_while_capture_is_adjusted(tmp_path):
    (r, a), s = contended(tmp_path, lambda c: refund(c, 'c1', 'rA', 700), lambda c: adjust_capture(c, 'c1', 500))
    check_refund_vs_adjust(r, a, s)


def test_adjustment_paused_while_refund_commits(tmp_path):
    (a, r), s = contended(tmp_path, lambda c: adjust_capture(c, 'c1', 500), lambda c: refund(c, 'c1', 'rA', 700))
    check_refund_vs_adjust(r, a, s)


def test_refund_paused_while_capture_is_voided(tmp_path):
    (r, v), s = contended(tmp_path, lambda c: refund(c, 'c1', 'rA', 300), lambda c: void_remaining(c, 'c1'))
    check_refund_vs_void(r, v, s)


def test_void_paused_while_refund_commits(tmp_path):
    (v, r), s = contended(tmp_path, lambda c: void_remaining(c, 'c1'), lambda c: refund(c, 'c1', 'rA', 300))
    check_refund_vs_void(r, v, s)
