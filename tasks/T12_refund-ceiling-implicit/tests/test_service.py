import sqlite3,threading,pytest
from service import setup,refund

def db(tmp_path):
    p=tmp_path/'refund.db';c=sqlite3.connect(p,timeout=10);setup(c)
    c.executemany('INSERT INTO captures VALUES(?,?,?)',[('c1','alice',1000),('c2','alice',500)])
    c.execute('INSERT INTO balances VALUES(?,?)',('alice',0));c.commit();return p,c

def test_ceiling_replay_and_conflicts(tmp_path):
    _,c=db(tmp_path)
    assert refund(c,'c1','r1',400)=={'receipt_id':'ref_r1','capture_id':'c1','amount_cents':400,'status':'refunded'}
    assert refund(c,'c1','r1',400)['receipt_id']=='ref_r1'
    with pytest.raises(ValueError):refund(c,'c1','r1',500)
    with pytest.raises(ValueError):refund(c,'c2','r1',400)
    assert refund(c,'c1','r2',600)['amount_cents']==600
    with pytest.raises(ValueError):refund(c,'c1','r3',1)
    assert c.execute("SELECT available_cents FROM balances WHERE account_id='alice'").fetchone()[0]==1000
    assert c.execute('SELECT count(*) FROM refunds').fetchone()[0]==2

def test_invalid_refunds_leave_no_changes(tmp_path):
    _,c=db(tmp_path)
    for cid,key,amt in [('none','x',2),('c1','',3),('c1','x',0),('c1','x',True),('c1','x',1001)]:
        with pytest.raises(ValueError):refund(c,cid,key,amt)
    assert c.execute('SELECT count(*) FROM refunds').fetchone()[0]==0
    assert c.execute('SELECT available_cents FROM balances').fetchone()[0]==0

def test_injected_partial_write_failure_rolls_back(tmp_path):
    _,c=db(tmp_path)
    c.execute("CREATE TRIGGER fail_refund BEFORE INSERT ON refunds BEGIN SELECT RAISE(ABORT, 'injected refund receipt failure'); END;")
    c.commit()
    with pytest.raises(sqlite3.DatabaseError):refund(c,'c1','failure',200)
    assert c.execute("SELECT available_cents FROM balances WHERE account_id='alice'").fetchone()[0]==0
    assert c.execute('SELECT count(*) FROM refunds').fetchone()[0]==0

from race_probe import pair_on_file, permissible_error

def test_competing_refunds_cannot_overrefund(tmp_path):
    path, seed = db(tmp_path)
    seed.close()
    outcomes = pair_on_file(
        path,
        lambda conn: refund(conn, 'c1', 'rA', 700),
        lambda conn: refund(conn, 'c1', 'rB', 700),
        lambda sql: 'from refunds' in sql and 'sum(' in sql,
    )
    for result, err in outcomes:
        assert permissible_error(err), f'unexpected competing refund error: {err!r}'
        if result is not None:
            assert result['status'] == 'refunded' and result['amount_cents'] == 700
    with sqlite3.connect(path, timeout=5) as conn:
        total = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?', ('c1',)).fetchone()[0]
        credited = conn.execute("SELECT available_cents FROM balances WHERE account_id='alice'").fetchone()[0]
        assert total <= 1000, 'committed refund ceiling exceeded'
        assert credited == total, 'refund accounting diverged from committed receipts'
        if total == 0:
            refund(conn, 'c1', 'rA', 700)  # safe retry after allowed lock timeouts
        total = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?', ('c1',)).fetchone()[0]
        assert total == 700
        assert conn.execute("SELECT available_cents FROM balances WHERE account_id='alice'").fetchone()[0] == 700
        assert conn.execute('SELECT COUNT(*) FROM refunds WHERE capture_id=?', ('c1',)).fetchone()[0] == 1
        with pytest.raises(ValueError):
            refund(conn, 'c1', 'extra', 400)
