def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _validate(capture_id, refund_key, amount_cents):
    if not isinstance(capture_id, str) or capture_id == '':
        raise ValueError('capture_id must be a nonempty string')
    if not isinstance(refund_key, str) or refund_key == '':
        raise ValueError('refund_key must be a nonempty string')
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError('amount_cents must be a positive integer')


def refund(conn, capture_id, refund_key, amount_cents):
    _validate(capture_id, refund_key, amount_cents)
    # Finish any implicit transaction the caller may have left open, then take
    # the write lock up front so that the check-then-write below is atomic
    # across independent connections. BEGIN IMMEDIATE honours the busy timeout
    # and raises sqlite3.OperationalError without changes if it cannot lock.
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    try:
        existing = conn.execute(
            'SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',
            (refund_key,)).fetchone()
        if existing is not None:
            if existing[0] != capture_id or existing[1] != amount_cents:
                raise ValueError('refund_key already used with a different payload')
            conn.rollback()
            return {'receipt_id': existing[2], 'capture_id': existing[0],
                    'amount_cents': existing[1], 'status': 'refunded'}

        capture = conn.execute(
            'SELECT account_id,amount_cents FROM captures WHERE capture_id=?',
            (capture_id,)).fetchone()
        if capture is None:
            raise ValueError('missing capture')
        account_id, captured_cents = capture[0], capture[1]

        balance = conn.execute(
            'SELECT available_cents FROM balances WHERE account_id=?',
            (account_id,)).fetchone()
        if balance is None:
            raise ValueError('missing balance')

        refunded_so_far = conn.execute(
            'SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',
            (capture_id,)).fetchone()[0]
        if refunded_so_far + amount_cents > captured_cents:
            raise ValueError('refund exceeds captured amount')

        receipt_id = 'ref_' + refund_key
        conn.execute(
            'UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',
            (amount_cents, account_id))
        conn.execute('INSERT INTO refunds VALUES(?,?,?,?)',
                     (refund_key, capture_id, amount_cents, receipt_id))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return {'receipt_id': receipt_id, 'capture_id': capture_id,
            'amount_cents': amount_cents, 'status': 'refunded'}
