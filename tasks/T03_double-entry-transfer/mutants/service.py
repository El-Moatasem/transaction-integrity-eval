from decimal import Decimal

def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));""");conn.commit()

def post_transfer(conn,transfer_id,source,target,amount,currency):
    try:d=Decimal(amount)
    except Exception:raise ValueError()
    if d<=0 or source==target:raise ValueError()
    minor=int(d*100)
    try:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM transfers WHERE transfer_id=?',(transfer_id,)).fetchone():
            conn.commit();return {'transfer_id':transfer_id,'amount_minor':minor,'entry_count':2}
        rows=conn.execute('SELECT currency FROM accounts WHERE account_id IN (?,?)',(source,target)).fetchall()
        if len(rows)!=2 or any(r[0]!=currency for r in rows):raise ValueError()
        conn.execute('INSERT INTO transfers VALUES(?,?,?,?,?)',(transfer_id,source,target,currency,minor))
        conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,source,'debit',minor,currency))
        conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,target,'credit',minor,currency))
        conn.commit();return {'transfer_id':transfer_id,'amount_minor':minor,'entry_count':2}
    except BaseException:
        conn.rollback();raise
