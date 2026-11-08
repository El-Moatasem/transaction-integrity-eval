def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""");conn.commit()


def _require_nonempty_text(value, name):
    if not isinstance(value, str) or value == '':
        raise ValueError(f'{name} must be a nonempty string')


def refund(conn, capture_id, refund_key, amount_cents):
    # Input validation happens before any transaction is opened, so invalid
    # attempts never touch the database.
    _require_nonempty_text(capture_id, 'capture_id')
    _require_nonempty_text(refund_key, 'refund_key')
    if type(amount_cents) is not int or amount_cents <= 0:
        raise ValueError('amount_cents must be a positive integer')

    if conn.in_transaction:
        conn.commit()

    try:
        # BEGIN IMMEDIATE takes the write lock up front, so the read-check-write
        # sequence below is serialized against other connections. The busy
        # timeout configured on the connection bounds how long we wait.
        conn.execute('BEGIN IMMEDIATE')

        existing = conn.execute(
            'SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',
            (refund_key,),
        ).fetchone()
        if existing is not None:
            if existing[0] != capture_id or existing[1] != amount_cents:
                raise ValueError('refund_key already used with a different payload')
            conn.commit()  # replay: no changes
            return {
                'receipt_id': existing[2],
                'capture_id': existing[0],
                'amount_cents': existing[1],
                'status': 'refunded',
            }

        capture = conn.execute(
            'SELECT account_id,amount_cents FROM captures WHERE capture_id=?',
            (capture_id,),
        ).fetchone()
        if capture is None:
            raise ValueError('missing capture')
        account_id, captured_cents = capture

        if conn.execute(
            'SELECT 1 FROM balances WHERE account_id=?', (account_id,)
        ).fetchone() is None:
            raise ValueError('missing balance')

        refunded_cents = conn.execute(
            'SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',
            (capture_id,),
        ).fetchone()[0]
        if refunded_cents + amount_cents > captured_cents:
            raise ValueError('refund exceeds captured amount')

        conn.execute(
            'UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',
            (amount_cents, account_id),
        )
        receipt_id = 'ref_' + refund_key
        conn.execute(
            'INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
            (refund_key, capture_id, amount_cents, receipt_id),
        )
        conn.commit()
        return {
            'receipt_id': receipt_id,
            'capture_id': capture_id,
            'amount_cents': amount_cents,
            'status': 'refunded',
        }
    except BaseException:
        # Roll back everything from this call (validation errors, lock
        # timeouts, and unexpected SQLite errors alike), then re-raise unchanged.
        if conn.in_transaction:
            conn.rollback()
        raise
