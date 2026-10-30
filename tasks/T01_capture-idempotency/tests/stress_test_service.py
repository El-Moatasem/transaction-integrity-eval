# Supplementary stress only. Not used by the deterministic gating grader.
# Racy tests may exhibit scheduling-related variability and need repeated audit.
import sqlite3
import threading
from service import setup, capture

def db(tmp_path):
    p=tmp_path/'pay.db'; conn=sqlite3.connect(p,timeout=8);setup(conn)
    conn.execute('INSERT INTO accounts VALUES(?,?)',('alice',1000));conn.execute('INSERT INTO accounts VALUES(?,?)',('bob',600));conn.commit();return p,conn

def test_concurrent_same_key(tmp_path):
    p,c=db(tmp_path);c.close();results=[];errors=[]
    def worker():
        con=sqlite3.connect(p,timeout=10)
        try: results.append(capture(con,'shared','alice',300))
        except Exception as e: errors.append(repr(e))
        finally: con.close()
    threads=[threading.Thread(target=worker) for _ in range(4)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert not errors and len(results)==4 and len({r['receipt_id'] for r in results})==1
    con=sqlite3.connect(p);assert con.execute("SELECT balance_cents FROM accounts WHERE account_id='alice'").fetchone()[0]==700
    assert con.execute('SELECT count(*) FROM captures').fetchone()[0]==1
