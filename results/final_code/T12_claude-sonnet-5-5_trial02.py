def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""");conn.commit()

def refund(conn,capture_id,refund_key,amount_cents):
    if not isinstance(capture_id,str) or not capture_id or not isinstance(refund_key,str) or not refund_key:
        raise ValueError('invalid id')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('BEGIN IMMEDIATE')
    try:
        existing=conn.execute('SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',(refund_key,)).fetchone()
        if existing:
            if existing[0]!=capture_id or existing[1]!=amount_cents or isinstance(amount_cents,bool):
                raise ValueError('refund key reused with different payload')
            result={'receipt_id':existing[2],'capture_id':existing[0],'amount_cents':existing[1],'status':'refunded'}
        else:
            if not isinstance(amount_cents,int) or isinstance(amount_cents,bool) or amount_cents<=0:
                raise ValueError('invalid amount')
            capture=conn.execute('SELECT account_id,amount_cents FROM captures WHERE capture_id=?',(capture_id,)).fetchone()
            if capture is None:raise ValueError('missing capture')
            if conn.execute('SELECT 1 FROM balances WHERE account_id=?',(capture[0],)).fetchone() is None:
                raise ValueError('missing balance')
            prior=conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',(capture_id,)).fetchone()[0]
            if prior+amount_cents>capture[1]:raise ValueError('exceeds captured amount')
            receipt='ref_'+refund_key
            conn.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',(amount_cents,capture[0]))
            conn.execute('INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',(refund_key,capture_id,amount_cents,receipt))
            result={'receipt_id':receipt,'capture_id':capture_id,'amount_cents':amount_cents,'status':'refunded'}
        conn.commit()
        return result
    except BaseException:
        conn.rollback()
        raise
