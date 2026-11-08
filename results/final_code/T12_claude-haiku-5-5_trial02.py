def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""");conn.commit()

def _result(receipt_id, capture_id, amount_cents):
    return {'receipt_id': receipt_id, 'capture_id': capture_id, 'amount_cents': amount_cents, 'status': 'refunded'}

def _refund_locked(conn, capture_id, refund_key, amount_cents):
    # Runs inside the write transaction, so the checks and writes are atomic
    # with respect to other worker connections.
    existing = conn.execute(
        'SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?', (refund_key,)).fetchone()
    if existing is not None:
        if existing[0] != capture_id or existing[1] != amount_cents:
            raise ValueError('refund_key reused with a different payload')
        return _result(existing[2], existing[0], existing[1])

    capture = conn.execute(
        'SELECT account_id,amount_cents FROM captures WHERE capture_id=?', (capture_id,)).fetchone()
    if capture is None:
        raise ValueError('missing capture')
    account_id, captured_cents = capture

    if conn.execute('SELECT 1 FROM balances WHERE account_id=?', (account_id,)).fetchone() is None:
        raise ValueError('missing balance')

    refunded_cents = conn.execute(
        'SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?', (capture_id,)).fetchone()[0]
    if refunded_cents + amount_cents > captured_cents:
        raise ValueError('refund exceeds captured amount')

    receipt_id = 'ref_' + refund_key
    cur = conn.execute(
        'UPDATE balances SET available_cents=available_cents+? WHERE account_id=?', (amount_cents, account_id))
    if cur.rowcount != 1:
        raise ValueError('missing balance')
    conn.execute(
        'INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
        (refund_key, capture_id, amount_cents, receipt_id))
    return _result(receipt_id, capture_id, amount_cents)

def refund(conn, capture_id, refund_key, amount_cents):
    if not isinstance(capture_id, str) or not capture_id:
        raise ValueError('capture_id must be a nonempty string')
    if not isinstance(refund_key, str) or not refund_key:
        raise ValueError('refund_key must be a nonempty string')
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError('amount_cents must be a positive integer')

    # BEGIN IMMEDIATE takes the write lock up front, so no other worker can
    # interleave between the cap check and the insert. If the lock cannot be
    # obtained within the connection's busy timeout, sqlite3.OperationalError
    # propagates and nothing has been changed.
    conn.execute('BEGIN IMMEDIATE')
    try:
        result = _refund_locked(conn, capture_id, refund_key, amount_cents)
        conn.commit()
        return result
    except BaseException:
        # Leave no partial changes on any failure (ValueError or SQLite error).
        if conn.in_transaction:
            conn.rollback()
        raise
