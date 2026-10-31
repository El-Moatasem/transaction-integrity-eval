import sqlite3

def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()

def capture(conn, key, account_id, amount_cents):
    row = conn.execute('SELECT account_id,amount_cents,receipt_id FROM captures WHERE key=?',(key,)).fetchone()
    if row:
        return {"receipt_id":row[2],"account_id":row[0],"amount_cents":row[1],"status":"captured"}
    conn.execute('UPDATE accounts SET balance_cents=balance_cents-? WHERE account_id=?',(amount_cents,account_id))
    receipt='cap_'+key
    conn.execute('INSERT INTO captures VALUES(?,?,?,?)',(key,account_id,amount_cents,receipt))
    conn.commit()
    return {"receipt_id":receipt,"account_id":account_id,"amount_cents":amount_cents,"status":"captured"}
