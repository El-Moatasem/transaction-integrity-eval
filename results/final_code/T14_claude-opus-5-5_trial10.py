import sqlite3

_MAX_INT = 2**63 - 1
_BUSY_TIMEOUT_MS = 5000


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,voided INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _is_amount(value):
    return type(value) is int and value <= _MAX_INT


def _refunded(conn, capture_id):
    return conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?', (capture_id,)).fetchone()[0]


def _begin(conn):
    # Take the write lock up front so every check and write below is
    # serialized against other workers (no check-then-act races).
    if conn.in_transaction:
        conn.commit()
    conn.execute('PRAGMA busy_timeout=%d' % _BUSY_TIMEOUT_MS)
    conn.execute('BEGIN IMMEDIATE')


def _rollback(conn):
    try:
        if conn.in_transaction:
            conn.rollback()
    except sqlite3.Error:
        pass


def refund(conn, capture_id, refund_key, amount_cents):
    if (not isinstance(capture_id, str) or not capture_id or not isinstance(refund_key, str) or not refund_key
            or not _is_amount(amount_cents) or amount_cents <= 0):
        raise ValueError('invalid refund')
    _begin(conn)
    try:
        prior = conn.execute('SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?', (refund_key,)).fetchone()
        if prior:
            if prior[0] != capture_id or prior[1] != amount_cents:
                raise ValueError('idempotency conflict')
            conn.rollback()
            return {'receipt_id': prior[2], 'capture_id': prior[0], 'amount_cents': prior[1], 'status': 'refunded'}
        capture = conn.execute('SELECT account_id,amount_cents,voided FROM captures WHERE capture_id=?', (capture_id,)).fetchone()
        if not capture:
            raise ValueError('missing capture')
        account, cap_amount, voided = capture
        if voided:
            raise ValueError('capture voided')
        if cap_amount is None or _refunded(conn, capture_id) + amount_cents > cap_amount:
            raise ValueError('refund exceeds capture')
        bal = conn.execute('SELECT available_cents FROM balances WHERE account_id=?', (account,)).fetchone()
        if bal is None or bal[0] is None:
            raise ValueError('missing balance')
        if bal[0] + amount_cents > _MAX_INT:
            raise ValueError('balance overflow')
        updated = conn.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?', (amount_cents, account))
        if updated.rowcount != 1:
            raise ValueError('missing balance')
        receipt = 'ref_' + refund_key
        conn.execute('INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
                     (refund_key, capture_id, amount_cents, receipt))
        conn.commit()
        return {'receipt_id': receipt, 'capture_id': capture_id, 'amount_cents': amount_cents, 'status': 'refunded'}
    except BaseException:
        _rollback(conn)
        raise


def adjust_capture(conn, capture_id, new_amount_cents):
    if not isinstance(capture_id, str) or not capture_id or not _is_amount(new_amount_cents) or new_amount_cents < 0:
        raise ValueError('invalid adjustment')
    _begin(conn)
    try:
        capture = conn.execute('SELECT amount_cents,voided FROM captures WHERE capture_id=?', (capture_id,)).fetchone()
        if not capture:
            raise ValueError('missing capture')
        if capture[1]:
            raise ValueError('capture voided')
        if capture[0] is None or new_amount_cents > capture[0]:
            raise ValueError('adjustment may only lower the captured amount')
        if new_amount_cents < _refunded(conn, capture_id):
            raise ValueError('below refunded total')
        conn.execute('UPDATE captures SET amount_cents=? WHERE capture_id=?', (new_amount_cents, capture_id))
        conn.commit()
        return {'capture_id': capture_id, 'amount_cents': new_amount_cents, 'status': 'adjusted'}
    except BaseException:
        _rollback(conn)
        raise


def void_remaining(conn, capture_id):
    if not isinstance(capture_id, str) or not capture_id:
        raise ValueError('invalid capture id')
    _begin(conn)
    try:
        capture = conn.execute('SELECT amount_cents,voided FROM captures WHERE capture_id=?', (capture_id,)).fetchone()
        if not capture:
            raise ValueError('missing capture')
        refunded = _refunded(conn, capture_id)
        if not capture[1]:
            conn.execute('UPDATE captures SET voided=1 WHERE capture_id=?', (capture_id,))
        conn.commit()
        return {'capture_id': capture_id, 'status': 'voided', 'refunded_cents': refunded, 'voided_cents': capture[0] - refunded}
    except BaseException:
        _rollback(conn)
        raise
