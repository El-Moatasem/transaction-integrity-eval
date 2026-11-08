def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()

def capture(conn,key,account_id,amount_cents):
    if not key or type(amount_cents) is not int or amount_cents<=0:raise ValueError()
    conn.execute('BEGIN IMMEDIATE')
    try:
        row=conn.execute('SELECT account_id,amount_cents,receipt_id FROM captures WHERE key=?',(key,)).fetchone()
        if row:
            if row[0]!=account_id and row[1]!=amount_cents:raise ValueError('conflict')
            result={'receipt_id':row[2],'account_id':row[0],'amount_cents':row[1],'status':'captured'}
        else:
            bal=conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?',(account_id,)).fetchone()
            if not bal or bal[0]<amount_cents:raise ValueError('funds')
            conn.execute('UPDATE accounts SET balance_cents=balance_cents-? WHERE account_id=?',(amount_cents,account_id))
            conn.execute('INSERT INTO captures VALUES(?,?,?,?)',(key,account_id,amount_cents,'cap_'+key))
            result={'receipt_id':'cap_'+key,'account_id':account_id,'amount_cents':amount_cents,'status':'captured'}
        conn.commit();return result
    except BaseException:
        conn.rollback();raise
