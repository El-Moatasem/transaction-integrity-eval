def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,voided INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""");conn.commit()


def _begin(conn):
    """Start a write transaction so that all reads and checks are serialized
    against concurrent writers (other processes/connections)."""
    if conn.in_transaction:
        conn.commit()
    mode = getattr(conn, 'autocommit', None)
    if mode is False:
        # PEP 249 mode: a deferred transaction is always open; escalate it to a
        # write transaction before reading anything.
        if not conn.in_transaction:
            conn.execute('BEGIN')
        conn.execute('UPDATE captures SET voided=voided WHERE 0')
    else:
        conn.execute('BEGIN IMMEDIATE')


def _begin_safe(conn):
    try:
        _begin(conn)
    except BaseException:
        _rollback(conn)
        raise


def _commit(conn):
    if getattr(conn, 'autocommit', None) is True:
        if conn.in_transaction:
            conn.execute('COMMIT')
    else:
        conn.commit()


def _rollback(conn):
    _begin_safe(conn)
    try:
        if getattr(conn, 'autocommit', None) is True:
            if conn.in_transaction:
                conn.execute('ROLLBACK')
        else:
            conn.rollback()
    except Exception:
        pass


def _is_amount(value):
    return type(value) is int


def _refunded(conn,capture_id):
    return conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?',(capture_id,)).fetchone()[0]


def refund(conn,capture_id,refund_key,amount_cents):
    if not isinstance(capture_id,str) or not capture_id or not isinstance(refund_key,str) or not refund_key or not _is_amount(amount_cents) or amount_cents<=0:
        raise ValueError('invalid refund')
    _begin_safe(conn)
    try:
        prior=conn.execute('SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?',(refund_key,)).fetchone()
        if prior:
            if prior[0]!=capture_id or prior[1]!=amount_cents:raise ValueError('idempotency conflict')
            _commit(conn)
            return {'receipt_id':prior[2],'capture_id':prior[0],'amount_cents':prior[1],'status':'refunded'}
        capture=conn.execute('SELECT account_id,amount_cents,voided FROM captures WHERE capture_id=?',(capture_id,)).fetchone()
        if not capture:raise ValueError('missing capture')
        account,cap_amount,voided=capture
        if voided:raise ValueError('capture voided')
        if cap_amount is None:raise ValueError('invalid capture amount')
        bal=conn.execute('SELECT available_cents FROM balances WHERE account_id=?',(account,)).fetchone()
        if bal is None or bal[0] is None:raise ValueError('missing balance')
        if _refunded(conn,capture_id)+amount_cents>cap_amount:raise ValueError('refund exceeds capture')
        updated=conn.execute('UPDATE balances SET available_cents=available_cents+? WHERE account_id=?',(amount_cents,account))
        if updated.rowcount!=1:raise ValueError('missing balance')
        conn.execute('INSERT INTO refunds VALUES(?,?,?,?)',(refund_key,capture_id,amount_cents,'ref_'+refund_key))
        _commit(conn)
        return {'receipt_id':'ref_'+refund_key,'capture_id':capture_id,'amount_cents':amount_cents,'status':'refunded'}
    except BaseException:
        _rollback(conn);raise


def adjust_capture(conn,capture_id,new_amount_cents):
    if not isinstance(capture_id,str) or not capture_id or not _is_amount(new_amount_cents) or new_amount_cents<0:
        raise ValueError('invalid adjustment')
    _begin_safe(conn)
    try:
        capture=conn.execute('SELECT amount_cents,voided FROM captures WHERE capture_id=?',(capture_id,)).fetchone()
        if not capture:raise ValueError('missing capture')
        if capture[1]:raise ValueError('capture voided')
        if new_amount_cents>capture[0]:raise ValueError('adjustment may only lower the captured amount')
        if new_amount_cents<_refunded(conn,capture_id):raise ValueError('below refunded total')
        conn.execute('UPDATE captures SET amount_cents=? WHERE capture_id=?',(new_amount_cents,capture_id))
        _commit(conn)
        return {'capture_id':capture_id,'amount_cents':new_amount_cents,'status':'adjusted'}
    except BaseException:
        _rollback(conn);raise


def void_remaining(conn,capture_id):
    if not isinstance(capture_id,str) or not capture_id:
        raise ValueError('invalid capture id')
    _begin_safe(conn)
    try:
        capture=conn.execute('SELECT amount_cents,voided FROM captures WHERE capture_id=?',(capture_id,)).fetchone()
        if not capture:raise ValueError('missing capture')
        refunded=_refunded(conn,capture_id)
        if not capture[1]:
            conn.execute('UPDATE captures SET voided=1 WHERE capture_id=?',(capture_id,))
        _commit(conn)
        return {'capture_id':capture_id,'status':'voided','refunded_cents':refunded,'voided_cents':capture[0]-refunded}
    except BaseException:
        _rollback(conn);raise
