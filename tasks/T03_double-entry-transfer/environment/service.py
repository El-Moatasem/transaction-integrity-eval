def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));""");conn.commit()

def post_transfer(conn,transfer_id,source,target,amount,currency):
    minor=int(float(amount)*100)
    existing=conn.execute('SELECT amount_minor FROM transfers WHERE transfer_id=?',(transfer_id,)).fetchone()
    if existing:return {'transfer_id':transfer_id,'amount_minor':existing[0],'entry_count':2}
    conn.execute('INSERT INTO transfers VALUES(?,?,?,?,?)',(transfer_id,source,target,currency,minor))
    conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,source,'debit',minor,currency))
    conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,target,'credit',minor,currency))
    conn.commit();return {'transfer_id':transfer_id,'amount_minor':minor,'entry_count':2}
