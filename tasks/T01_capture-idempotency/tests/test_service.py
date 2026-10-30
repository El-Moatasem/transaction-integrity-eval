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
