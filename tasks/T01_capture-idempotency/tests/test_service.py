import sqlite3, pytest, threading
from service import setup,capture

def db(tmp_path):
    p=tmp_path/'pay.db'; conn=sqlite3.connect(p,timeout=8);setup(conn)
    conn.execute('INSERT INTO accounts VALUES(?,?)',('alice',1000));conn.execute('INSERT INTO accounts VALUES(?,?)',('bob',600));conn.commit();return p,conn

def test_exact_replay_and_conflict(tmp_path):
    p,c=db(tmp_path)
    expected={'receipt_id':'cap_one','account_id':'alice','amount_cents':250,'status':'captured'}
    assert capture(c,'one','alice',250)==expected
    assert capture(c,'one','alice',250)==expected
    for a,amt in [('alice',251),('bob',250)]:
        with pytest.raises(ValueError):capture(c,'one',a,amt)
    assert c.execute("SELECT balance_cents FROM accounts WHERE account_id='alice'").fetchone()[0]==750
    assert c.execute('SELECT count(*) FROM captures').fetchone()[0]==1

def test_validation_and_atomicity(tmp_path):
    p,c=db(tmp_path)
    for key,owner,amount in [('', 'alice',1),('x','alice',0),('x','alice',True),('x','alice',1001),('x','none',10)]:
        with pytest.raises(ValueError):capture(c,key,owner,amount)
    assert c.execute("SELECT balance_cents FROM accounts WHERE account_id='alice'").fetchone()[0]==1000
    assert c.execute('SELECT count(*) FROM captures').fetchone()[0]==0

def test_injected_partial_write_failure_rolls_back(tmp_path):
    _,c=db(tmp_path)
    c.execute("CREATE TRIGGER fail_capture BEFORE INSERT ON captures BEGIN SELECT RAISE(ABORT, 'injected receipt failure'); END;")
    c.commit()
    with pytest.raises(sqlite3.DatabaseError):capture(c,'failure','alice',200)
    assert c.execute("SELECT balance_cents FROM accounts WHERE account_id='alice'").fetchone()[0]==1000
    assert c.execute('SELECT count(*) FROM captures').fetchone()[0]==0

from race_probe import pair_on_file, permissible_error

def test_competing_identical_capture_across_connections(tmp_path):
    path, seed = db(tmp_path)
    seed.close()
    outcomes = pair_on_file(
        path,
        lambda conn: capture(conn, 'shared', 'alice', 300),
        lambda conn: capture(conn, 'shared', 'alice', 300),
        lambda sql: 'from captures' in sql and 'where key' in sql,
    )
    for result, err in outcomes:
        # A same-key, same-payload request must replay or encounter a permitted
        # SQLite lock timeout; ValueError is not allowed for an identical replay.
        assert err is None or (permissible_error(err) and not isinstance(err, ValueError)), \
            f'unexpected competing capture error: {err!r}' 
        if result is not None:
            assert result == {'receipt_id': 'cap_shared', 'account_id': 'alice',
                              'amount_cents': 300, 'status': 'captured'}
    assert any(err is None for _, err in outcomes)
    with sqlite3.connect(path, timeout=5) as conn:
        assert conn.execute("SELECT balance_cents FROM accounts WHERE account_id='alice'").fetchone()[0] == 700
        assert conn.execute('SELECT COUNT(*) FROM captures').fetchone()[0] == 1
        assert capture(conn, 'shared', 'alice', 300)['receipt_id'] == 'cap_shared'
        assert conn.execute("SELECT balance_cents FROM accounts WHERE account_id='alice'").fetchone()[0] == 700
