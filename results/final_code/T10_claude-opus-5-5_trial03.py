import json
import sqlite3

TOPIC = 'account.changed'


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


def _manual_mode(conn):
    """True if the connection does not open transactions implicitly."""
    ac = getattr(conn, 'autocommit', None)
    if ac is True:
        return True
    if ac is False:
        return False
    return conn.isolation_level is None


def _begin(conn):
    """Start a write transaction, acquiring the write lock up front."""
    if _manual_mode(conn):
        if not conn.in_transaction:
            conn.execute('BEGIN IMMEDIATE')
            return
    elif not conn.in_transaction and getattr(conn, 'autocommit', None) is not False:
        # Legacy implicit mode: we may issue an explicit BEGIN ourselves.
        conn.execute('BEGIN IMMEDIATE')
        return
    # Already inside a (possibly deferred) transaction: take the write lock
    # immediately with a no-op write, before any reads.
    conn.execute('UPDATE outbox SET published=published WHERE 0')


def _run(conn, fn):
    _begin(conn)
    try:
        result = fn()
    except BaseException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    conn.commit()
    return result


def _valid_str(v):
    return isinstance(v, str) and v.strip() != ''


def apply_event(conn, event_id, account_id, delta_cents):
    if not _valid_str(event_id):
        raise ValueError('event_id must be a nonempty string')
    if not _valid_str(account_id):
        raise ValueError('account_id must be a nonempty string')
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int) or delta_cents == 0:
        raise ValueError('delta_cents must be a nonzero int')

    def work():
        row = conn.execute(
            'SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
            (event_id,)).fetchone()
        if row is not None:
            if row[0] == account_id and row[1] == delta_cents:
                return {'event_id': event_id, 'account_id': account_id,
                        'balance_after_cents': int(row[2])}
            raise ValueError('conflicting replay of event_id %r' % (event_id,))
        acc = conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?',
                           (account_id,)).fetchone()
        if acc is None:
            raise ValueError('unknown account %r' % (account_id,))
        balance = int(acc[0] or 0) + delta_cents
        if balance < 0:
            raise ValueError('insufficient funds')
        cur = conn.execute('UPDATE accounts SET balance_cents=? WHERE account_id=?',
                           (balance, account_id))
        if cur.rowcount != 1:
            raise sqlite3.DatabaseError('account update affected %d rows' % cur.rowcount)
        conn.execute('INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
                     (event_id, account_id, delta_cents, balance))
        payload = json.dumps({'event_id': event_id, 'account_id': account_id,
                              'delta_cents': delta_cents, 'balance_after_cents': balance},
                             sort_keys=True, separators=(',', ':'))
        conn.execute('INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
                     (event_id, TOPIC, payload))
        return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': balance}

    return _run(conn, work)


def get_pending(conn):
    rows = conn.execute(
        'SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id').fetchall()
    return [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]


def mark_published(conn, event_id):
    def work():
        row = conn.execute('SELECT published FROM outbox WHERE event_id=?', (event_id,)).fetchone()
        if row is None:
            raise ValueError('unknown event_id %r' % (event_id,))
        if row[0] != 1:
            conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))

    _run(conn, work)
