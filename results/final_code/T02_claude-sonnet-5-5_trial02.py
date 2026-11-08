def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _result(receipt_id, capture_id, amount):
    return {'receipt_id': receipt_id, 'capture_id': capture_id,
            'amount_cents': amount, 'status': 'refunded'}


def refund(conn, capture_id, refund_key, amount_cents):
    if not isinstance(capture_id, str) or not capture_id:
        raise ValueError('invalid capture_id')
    if not isinstance(refund_key, str) or not refund_key:
        raise ValueError('invalid refund_key')
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError('invalid amount')

    if conn.in_transaction:
        conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    try:
        existing = conn.execute(
            'SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',
            (refund_key,)).fetchone()
        if existing:
            if existing[0] != capture_id or existing[1] != amount_cents:
                raise ValueError('refund key reused with different payload')
            conn.rollback()
            return _result(existing[2], existing[0], existing[1])
        cap = conn.execute('SELECT account_id,amount_cents FROM captures WHERE capture_id=?',
                           (capture_id,)).fetchone()
        if cap is None:
            raise ValueError('missing capture')
        bal = conn.execute('SELECT 1 FROM balances WHERE account_id=?', (cap[0],)).fetchone()
        if bal is None:
            raise ValueError('missing balance')
        prior = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',
                             (capture_id,)).fetchone()[0]
        if prior + amount_cents > cap[1]:
            raise ValueError('refund exceeds captured amount')
        receipt = 'ref_' + refund_key
        conn.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',
                     (amount_cents, cap[0]))
        conn.execute('INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
                     (refund_key, capture_id, amount_cents, receipt))
        conn.commit()
        return _result(receipt, capture_id, amount_cents)
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
