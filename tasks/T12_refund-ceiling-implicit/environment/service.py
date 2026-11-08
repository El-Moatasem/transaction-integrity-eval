def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""");conn.commit()

def refund(conn,capture_id,refund_key,amount_cents):
    existing=conn.execute('SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',(refund_key,)).fetchone()
    if existing:
        return {'receipt_id':existing[2],'capture_id':existing[0],'amount_cents':existing[1],'status':'refunded'}
    capture=conn.execute('SELECT account_id FROM captures WHERE capture_id=?',(capture_id,)).fetchone()
    if capture is None:raise ValueError('missing capture')
    conn.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',(amount_cents,capture[0]))
    conn.execute('INSERT INTO refunds VALUES(?,?,?,?)',(refund_key,capture_id,amount_cents,'ref_'+refund_key));conn.commit()
    return {'receipt_id':'ref_'+refund_key,'capture_id':capture_id,'amount_cents':amount_cents,'status':'refunded'}
