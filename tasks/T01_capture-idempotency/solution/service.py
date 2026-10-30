def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()

def capture(conn, key, account_id, amount_cents):
    if not isinstance(key,str) or not key or not isinstance(account_id,str) or not account_id or type(amount_cents) is not int or amount_cents <= 0:
        raise ValueError('invalid capture')
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT account_id,amount_cents,receipt_id FROM captures WHERE key=?',(key,)).fetchone()
        if row:
            if row[0] != account_id or row[1] != amount_cents:
                raise ValueError('idempotency conflict')
            result={"receipt_id":row[2],"account_id":row[0],"amount_cents":row[1],"status":"captured"}
        else:
            account=conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?',(account_id,)).fetchone()
            if not account or account[0] < amount_cents:
                raise ValueError('account missing or insufficient funds')
            conn.execute('UPDATE accounts SET balance_cents=balance_cents-? WHERE account_id=?',(amount_cents,account_id))
            receipt='cap_'+key
            conn.execute('INSERT INTO captures VALUES(?,?,?,?)',(key,account_id,amount_cents,receipt))
            result={"receipt_id":receipt,"account_id":account_id,"amount_cents":amount_cents,"status":"captured"}
        conn.commit()
        return result
    except BaseException:
        conn.rollback()
        raise
