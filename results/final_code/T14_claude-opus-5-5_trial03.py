import sqlite3


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,voided INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _is_amount(value):
    return type(value) is int


def _is_id(value):
    return isinstance(value, str) and value != ''


def _refunded(conn, capture_id):
    return conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?', (capture_id,)).fetchone()[0]


def _run(conn, body):
    """Run body(conn) inside a single write-locked (BEGIN IMMEDIATE) transaction.

    All reads and checks happen while holding the write lock so concurrent
    workers cannot interleave check-then-write sequences. Any exception rolls
    back everything and propagates unchanged.
    """
    if conn.in_transaction:
        conn.commit()
    saved = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            result = body(conn)
            conn.execute('COMMIT')
            return result
        except BaseException:
            if conn.in_transaction:
                try:
                    conn.execute('ROLLBACK')
                except sqlite3.Error:
                    pass
            raise
    finally:
        conn.isolation_level = saved


def refund(conn, capture_id, refund_key, amount_cents):
    if not _is_id(capture_id) or not _is_id(refund_key) or not _is_amount(amount_cents) or amount_cents <= 0:
        raise ValueError('invalid refund')

    def body(c):
        prior = c.execute('SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?', (refund_key,)).fetchone()
        if prior:
            if prior[0] != capture_id or prior[1] != amount_cents:
                raise ValueError('idempotency conflict')
            return {'receipt_id': prior[2], 'capture_id': prior[0], 'amount_cents': prior[1], 'status': 'refunded'}
        capture = c.execute('SELECT account_id,amount_cents,voided FROM captures WHERE capture_id=?', (capture_id,)).fetchone()
        if not capture:
            raise ValueError('missing capture')
        account, cap_amount, voided = capture
        if voided:
            raise ValueError('capture voided')
        if not _is_amount(cap_amount):
            raise ValueError('invalid capture amount')
        if _refunded(c, capture_id) + amount_cents > cap_amount:
            raise ValueError('refund exceeds capture')
        bal = c.execute('SELECT available_cents FROM balances WHERE account_id=?', (account,)).fetchone()
        if bal is None or not _is_amount(bal[0]):
            raise ValueError('missing balance')
        receipt = 'ref_' + refund_key
        updated = c.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?', (amount_cents, account))
        if updated.rowcount != 1:
            raise ValueError('missing balance')
        c.execute('INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
                  (refund_key, capture_id, amount_cents, receipt))
        return {'receipt_id': receipt, 'capture_id': capture_id, 'amount_cents': amount_cents, 'status': 'refunded'}

    return _run(conn, body)


def adjust_capture(conn, capture_id, new_amount_cents):
    if not _is_id(capture_id) or not _is_amount(new_amount_cents) or new_amount_cents < 0:
        raise ValueError('invalid adjustment')

    def body(c):
        capture = c.execute('SELECT amount_cents,voided FROM captures WHERE capture_id=?', (capture_id,)).fetchone()
        if not capture:
            raise ValueError('missing capture')
        amount, voided = capture
        if voided:
            raise ValueError('capture voided')
        if not _is_amount(amount):
            raise ValueError('invalid capture amount')
        if new_amount_cents > amount:
            raise ValueError('adjustment may only lower the captured amount')
        if new_amount_cents < _refunded(c, capture_id):
            raise ValueError('below refunded total')
        c.execute('UPDATE captures SET amount_cents=? WHERE capture_id=?', (new_amount_cents, capture_id))
        return {'capture_id': capture_id, 'amount_cents': new_amount_cents, 'status': 'adjusted'}

    return _run(conn, body)


def void_remaining(conn, capture_id):
    if not _is_id(capture_id):
        raise ValueError('invalid capture id')

    def body(c):
        capture = c.execute('SELECT amount_cents,voided FROM captures WHERE capture_id=?', (capture_id,)).fetchone()
        if not capture:
            raise ValueError('missing capture')
        amount, voided = capture
        if not _is_amount(amount):
            raise ValueError('invalid capture amount')
        refunded = _refunded(c, capture_id)
        if not voided:
            c.execute('UPDATE captures SET voided=1 WHERE capture_id=?', (capture_id,))
        return {'capture_id': capture_id, 'status': 'voided', 'refunded_cents': refunded, 'voided_cents': amount - refunded}

    return _run(conn, body)
