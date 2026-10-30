# Supplementary stress only. Not used by the deterministic gating grader.
# Racy tests may exhibit scheduling-related variability and need repeated audit.
import sqlite3
import threading
from service import setup, refund

def db(tmp_path):
    p=tmp_path/'refund.db';c=sqlite3.connect(p,timeout=10);setup(c)
    c.executemany('INSERT INTO captures VALUES(?,?,?)',[('c1','alice',1000),('c2','alice',500)])
    c.execute('INSERT INTO balances VALUES(?,?)',('alice',0));c.commit();return p,c

def test_concurrent_refund_ceiling(tmp_path):
    p,c=db(tmp_path);c.close();ok=[];bad=[]
    def work(k):
        con=sqlite3.connect(p,timeout=10)
        try:ok.append(refund(con,'c1',k,700))
        except ValueError:bad.append(k)
        finally:con.close()
    ts=[threading.Thread(target=work,args=(f'r{i}',)) for i in range(3)]
    for t in ts:t.start()
    for t in ts:t.join()
    assert len(ok)==1 and len(bad)==2
    con=sqlite3.connect(p)
    assert con.execute('SELECT SUM(amount_cents) FROM refunds').fetchone()[0]==700
    assert con.execute('SELECT available_cents FROM balances').fetchone()[0]==700
