import sqlite3


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _result(receipt_id, capture_id, amount_cents):
    return {'receipt_id': receipt_id, 'capture_id': capture_id,
            'amount_cents': amount_cents, 'status': 'refunded'}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _begin(conn):
    """Start a write-locked unit of work. Returns a callable pair (commit, rollback)."""
    if not conn.in_transaction:
        conn.execute('BEGIN IMMEDIATE')

        def commit():
            conn.execute('COMMIT')

        def rollback():
            if conn.in_transaction:
                conn.execute('ROLLBACK')
        return commit, rollback

    # Caller already has an open transaction (e.g. autocommit=False mode):
    # nest with a savepoint and grab the write lock up front.
    conn.execute('SAVEPOINT refund_sp')

    def commit():
        conn.execute('RELEASE SAVEPOINT refund_sp')
        conn.commit()

    def rollback():
        if conn.in_transaction:
            conn.execute('ROLLBACK TO SAVEPOINT refund_sp')
            conn.execute('RELEASE SAVEPOINT refund_sp')
    try:
        # Acquire the write lock before reading (no-op write).
        conn.execute('UPDATE balances SET available_cents=available_cents WHERE 0')
    except BaseException:
        rollback()
        raise
    return commit, rollback


def refund(conn, capture_id: str, refund_key: str, amount_cents: int) -> dict:
    if not isinstance(capture_id, str) or not capture_id:
        raise ValueError('capture_id must be a nonempty string')
    if not isinstance(refund_key, str) or not refund_key:
        raise ValueError('refund_key must be a nonempty string')
    if not _is_int(amount_cents) or amount_cents <= 0:
        raise ValueError('amount_cents must be a positive integer')

    commit, rollback = _begin(conn)
    try:
        existing = conn.execute(
            'SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',
            (refund_key,)).fetchone()
        if existing is not None:
            if existing[0] != capture_id or existing[1] != amount_cents:
                raise ValueError('refund_key reused with different payload')
            rollback()
            return _result(existing[2], existing[0], existing[1])

        capture = conn.execute(
            'SELECT account_id,amount_cents FROM captures WHERE capture_id=?',
            (capture_id,)).fetchone()
        if capture is None:
            raise ValueError('missing capture')
        account_id, captured = capture
        if not _is_int(captured):
            raise ValueError('invalid capture amount')

        bal = conn.execute('SELECT available_cents FROM balances WHERE account_id=?',
                           (account_id,)).fetchone()
        if bal is None:
            raise ValueError('missing balance')

        already = conn.execute(
            'SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',
            (capture_id,)).fetchone()[0]
        if already + amount_cents > captured:
            raise ValueError('refund exceeds captured amount')

        cur = conn.execute(
            'UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',
            (amount_cents, account_id))
        if cur.rowcount != 1:
            raise sqlite3.DatabaseError('balance update affected unexpected rows')
        receipt_id = 'ref_' + refund_key
        conn.execute('INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
                     (refund_key, capture_id, amount_cents, receipt_id))
        commit()
    except BaseException:
        try:
            rollback()
        except sqlite3.Error:
            pass
        raise
    return _result(receipt_id, capture_id, amount_cents)
