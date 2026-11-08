import sqlite3

_BUSY_TIMEOUT_MS = 5000


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _result(receipt_id, capture_id, amount_cents):
    return {'receipt_id': receipt_id, 'capture_id': capture_id,
            'amount_cents': amount_cents, 'status': 'refunded'}


def _validate(capture_id, refund_key, amount_cents):
    if not isinstance(capture_id, str) or not capture_id:
        raise ValueError('capture_id must be a nonempty string')
    if not isinstance(refund_key, str) or not refund_key:
        raise ValueError('refund_key must be a nonempty string')
    if type(amount_cents) is not int or amount_cents <= 0:
        raise ValueError('amount_cents must be a positive integer')


def _ensure_bounded_wait(conn):
    try:
        cur = conn.execute('PRAGMA busy_timeout').fetchone()
        current = cur[0] if cur else 0
        if not current or current > _BUSY_TIMEOUT_MS:
            conn.execute('PRAGMA busy_timeout=%d' % _BUSY_TIMEOUT_MS)
    except sqlite3.Error:
        pass


def _do_refund(conn, capture_id, refund_key, amount_cents):
    existing = conn.execute(
        'SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',
        (refund_key,)).fetchone()
    if existing is not None:
        ex_capture, ex_amount, ex_receipt = existing
        if ex_capture != capture_id or ex_amount != amount_cents:
            raise ValueError('refund_key reused with different payload')
        return _result(ex_receipt, ex_capture, ex_amount), False

    capture = conn.execute(
        'SELECT account_id,amount_cents FROM captures WHERE capture_id=?',
        (capture_id,)).fetchone()
    if capture is None:
        raise ValueError('missing capture')
    account_id, captured = capture
    if type(captured) is not int:
        raise ValueError('invalid captured amount')

    balance = conn.execute(
        'SELECT available_cents FROM balances WHERE account_id=?',
        (account_id,)).fetchone()
    if balance is None or type(balance[0]) is not int:
        raise ValueError('missing balance')

    prior = conn.execute(
        'SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',
        (capture_id,)).fetchone()[0] or 0
    if prior + amount_cents > captured:
        raise ValueError('refund exceeds captured amount')

    receipt_id = 'ref_' + refund_key
    cur = conn.execute(
        'UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',
        (amount_cents, account_id))
    if cur.rowcount != 1:
        raise ValueError('missing balance')
    conn.execute(
        'INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
        (refund_key, capture_id, amount_cents, receipt_id))
    return _result(receipt_id, capture_id, amount_cents), True


def refund(conn, capture_id, refund_key, amount_cents):
    _validate(capture_id, refund_key, amount_cents)
    _ensure_bounded_wait(conn)

    if conn.in_transaction:
        # Caller already owns a transaction: use a savepoint so our changes
        # are atomic with respect to failures without committing theirs.
        conn.execute('SAVEPOINT refund_sp')
        try:
            result, _ = _do_refund(conn, capture_id, refund_key, amount_cents)
        except BaseException:
            try:
                conn.execute('ROLLBACK TO SAVEPOINT refund_sp')
                conn.execute('RELEASE SAVEPOINT refund_sp')
            except sqlite3.Error:
                pass
            raise
        conn.execute('RELEASE SAVEPOINT refund_sp')
        return result

    # Take the write lock up front so the ceiling check and the writes are
    # serialized across worker processes.
    conn.execute('BEGIN IMMEDIATE')
    try:
        result, _ = _do_refund(conn, capture_id, refund_key, amount_cents)
        conn.execute('COMMIT')
    except BaseException:
        if conn.in_transaction:
            try:
                conn.execute('ROLLBACK')
            except sqlite3.Error:
                pass
        raise
    return result
