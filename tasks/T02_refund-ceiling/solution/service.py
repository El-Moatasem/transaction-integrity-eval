def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""");conn.commit()

def refund(conn,capture_id,refund_key,amount_cents):
    if not isinstance(capture_id,str) or not capture_id or not isinstance(refund_key,str) or not refund_key or type(amount_cents) is not int or amount_cents<=0:
        raise ValueError('invalid refund')
    try:
        conn.execute('BEGIN IMMEDIATE')
        prior=conn.execute('SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',(refund_key,)).fetchone()
        if prior:
            if prior[0]!=capture_id or prior[1]!=amount_cents:raise ValueError('idempotency conflict')
            result={'receipt_id':prior[2],'capture_id':prior[0],'amount_cents':prior[1],'status':'refunded'}
        else:
            capture=conn.execute('SELECT account_id,amount_cents FROM captures WHERE capture_id=?',(capture_id,)).fetchone()
            if not capture:raise ValueError('missing capture')
            account,cap_amount=capture
            total=conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',(capture_id,)).fetchone()[0]
            if total+amount_cents>cap_amount:raise ValueError('refund exceeds capture')
            updated=conn.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',(amount_cents,account))
            if updated.rowcount!=1:raise ValueError('missing balance')
            conn.execute('INSERT INTO refunds VALUES(?,?,?,?)',(refund_key,capture_id,amount_cents,'ref_'+refund_key))
            result={'receipt_id':'ref_'+refund_key,'capture_id':capture_id,'amount_cents':amount_cents,'status':'refunded'}
        conn.commit();return result
    except BaseException:
        conn.rollback();raise
