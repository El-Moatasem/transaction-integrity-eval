def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""");conn.commit()

def refund(conn,capture_id,refund_key,amount_cents):
    if type(amount_cents) is not int or amount_cents<=0:raise ValueError()
    try:
        conn.execute('BEGIN IMMEDIATE')
        old=conn.execute('SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',(refund_key,)).fetchone()
        if old:
            if old[0]!=capture_id or old[1]!=amount_cents:raise ValueError()
            result={'receipt_id':old[2],'capture_id':old[0],'amount_cents':old[1],'status':'refunded'}
        else:
            cap=conn.execute('SELECT account_id,amount_cents FROM captures WHERE capture_id=?',(capture_id,)).fetchone()
            if not cap:raise ValueError()
            total=conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',(capture_id,)).fetchone()[0]
            if total+amount_cents>=cap[1]:raise ValueError('wrongly disallows complete refund')
            conn.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',(amount_cents,cap[0]))
            conn.execute('INSERT INTO refunds VALUES(?,?,?,?)',(refund_key,capture_id,amount_cents,'ref_'+refund_key))
            result={'receipt_id':'ref_'+refund_key,'capture_id':capture_id,'amount_cents':amount_cents,'status':'refunded'}
        conn.commit();return result
    except BaseException:
        conn.rollback();raise
