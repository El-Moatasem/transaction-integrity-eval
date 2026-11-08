import json
import sqlite3

TOPIC = 'account.changed'


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


def _begin_write(conn):
    """Start a transaction holding the write lock (works for all Python connection modes)."""
    if conn.in_transaction:
        conn.commit()
    if conn.in_transaction:
        # Python 3.12+ autocommit=False keeps a deferred transaction open implicitly;
        # take the write lock with a no-op write statement.
        conn.execute('UPDATE accounts SET balance_cents=balance_cents WHERE 0')
    else:
        conn.execute('BEGIN IMMEDIATE')


def _rollback(conn):
    try:
        conn.rollback()
    except sqlite3.Error:
        pass


def _nonempty_str(v):
    return isinstance(v, str) and v != ''


def apply_event(conn, event_id, account_id, delta_cents):
    if not _nonempty_str(event_id):
        raise ValueError('event_id must be a nonempty string')
    if not _nonempty_str(account_id):
        raise ValueError('account_id must be a nonempty string')
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int) or delta_cents == 0:
        raise ValueError('delta_cents must be a nonzero int')

    _begin_write(conn)
    try:
        row = conn.execute(
            'SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
            (event_id,)).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError('conflicting replay of event_id %r' % event_id)
            conn.rollback()
            return {'event_id': event_id, 'account_id': account_id,
                    'balance_after_cents': int(row[2])}

        acc = conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?',
                           (account_id,)).fetchone()
        if acc is None:
            raise ValueError('unknown account %r' % account_id)
        new_balance = int(acc[0]) + delta_cents
        if new_balance < 0:
            raise ValueError('insufficient funds')

        cur = conn.execute('UPDATE accounts SET balance_cents=? WHERE account_id=?',
                           (new_balance, account_id))
        if cur.rowcount != 1:
            raise sqlite3.DatabaseError('account update affected %d rows' % cur.rowcount)
        conn.execute('INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
                     (event_id, account_id, delta_cents, new_balance))
        payload = json.dumps({'event_id': event_id, 'account_id': account_id,
                              'delta_cents': delta_cents, 'balance_after_cents': new_balance},
                             sort_keys=True, separators=(',', ':'))
        conn.execute('INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
                     (event_id, TOPIC, payload))
        conn.commit()
    except BaseException:
        _rollback(conn)
        raise
    return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': new_balance}


def get_pending(conn):
    rows = conn.execute(
        'SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id').fetchall()
    return [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]


def mark_published(conn, event_id):
    if not _nonempty_str(event_id):
        raise ValueError('event_id must be a nonempty string')
    _begin_write(conn)
    try:
        row = conn.execute('SELECT published FROM outbox WHERE event_id=?', (event_id,)).fetchone()
        if row is None:
            raise ValueError('unknown event_id %r' % event_id)
        if row[0] != 1:
            conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
        conn.commit()
    except BaseException:
        _rollback(conn)
        raise
