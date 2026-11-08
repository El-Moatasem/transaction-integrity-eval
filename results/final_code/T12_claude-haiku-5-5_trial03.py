def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""");conn.commit()


def _validate(capture_id, refund_key, amount_cents):
    if not isinstance(capture_id, str) or not capture_id:
        raise ValueError('capture_id must be a nonempty string')
    if not isinstance(refund_key, str) or not refund_key:
        raise ValueError('refund_key must be a nonempty string')
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError('amount_cents must be a positive integer')


def _apply(conn, capture_id, refund_key, amount_cents):
    existing = conn.execute(
        'SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',
        (refund_key,)).fetchone()
    if existing is not None:
        if existing[0] != capture_id or existing[1] != amount_cents:
            raise ValueError('refund_key reused with a different payload')
        return {'receipt_id': existing[2], 'capture_id': existing[0],
                'amount_cents': existing[1], 'status': 'refunded'}

    capture = conn.execute(
        'SELECT account_id,amount_cents FROM captures WHERE capture_id=?',
        (capture_id,)).fetchone()
    if capture is None:
        raise ValueError('missing capture')
    account_id, captured = capture[0], capture[1]

    if conn.execute('SELECT 1 FROM balances WHERE account_id=?', (account_id,)).fetchone() is None:
        raise ValueError('missing balance')

    refunded = conn.execute(
        'SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',
        (capture_id,)).fetchone()[0]
    if refunded + amount_cents > captured:
        raise ValueError('refund would exceed captured amount')

    cur = conn.execute(
        'UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',
        (amount_cents, account_id))
    if cur.rowcount != 1:
        raise ValueError('missing balance')

    receipt_id = 'ref_' + refund_key
    conn.execute(
        'INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
        (refund_key, capture_id, amount_cents, receipt_id))
    return {'receipt_id': receipt_id, 'capture_id': capture_id,
            'amount_cents': amount_cents, 'status': 'refunded'}


def refund(conn, capture_id: str, refund_key: str, amount_cents: int) -> dict:
    _validate(capture_id, refund_key, amount_cents)

    # Finish any implicit transaction left by the caller so we can take the write lock up front.
    if conn.in_transaction:
        conn.commit()

    # Wait a bounded time for other worker processes instead of failing immediately or blocking forever.
    conn.execute('PRAGMA busy_timeout=5000')
    # BEGIN IMMEDIATE takes the write lock before any read, so the check-and-credit is atomic
    # across processes. If it fails (e.g. database busy), no transaction is open and nothing changed.
    conn.execute('BEGIN IMMEDIATE')
    try:
        result = _apply(conn, capture_id, refund_key, amount_cents)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return result
