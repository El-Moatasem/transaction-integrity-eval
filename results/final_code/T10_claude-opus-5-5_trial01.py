import json
import sqlite3

TOPIC = 'account.changed'
_INT64_MIN = -(2 ** 63)
_INT64_MAX = 2 ** 63 - 1


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


def _begin(conn):
    # Finish any implicit transaction left open by the caller, then take the
    # write lock up front so read-check-write is atomic across connections.
    if conn.in_transaction:
        conn.commit()
    conn.execute('BEGIN IMMEDIATE')


def _rollback(conn):
    try:
        if conn.in_transaction:
            conn.rollback()
    except sqlite3.Error:
        pass


def _validate(event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError('event_id must be a nonempty string')
    if not isinstance(account_id, str) or not account_id:
        raise ValueError('account_id must be a nonempty string')
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int):
        raise ValueError('delta_cents must be an int')
    if delta_cents == 0:
        raise ValueError('delta_cents must be nonzero')
    if not (_INT64_MIN <= delta_cents <= _INT64_MAX):
        raise ValueError('delta_cents out of range')


def _payload(event_id, account_id, delta_cents, balance_after):
    return json.dumps({'event_id': event_id, 'account_id': account_id,
                       'delta_cents': delta_cents,
                       'balance_after_cents': balance_after}, sort_keys=True)


def apply_event(conn, event_id, account_id, delta_cents):
    _validate(event_id, account_id, delta_cents)
    _begin(conn)
    try:
        row = conn.execute('SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
                           (event_id,)).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError('conflicting replay of event_id')
            conn.rollback()
            return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': int(row[2])}
        acc = conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?', (account_id,)).fetchone()
        if acc is None:
            raise ValueError('unknown account')
        balance = int(acc[0]) + delta_cents
        if balance < 0:
            raise ValueError('insufficient funds')
        if balance > _INT64_MAX:
            raise ValueError('balance overflow')
        cur = conn.execute('UPDATE accounts SET balance_cents=? WHERE account_id=?', (balance, account_id))
        if cur.rowcount != 1:
            raise sqlite3.DatabaseError('account update affected unexpected row count')
        conn.execute('INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
                     (event_id, account_id, delta_cents, balance))
        conn.execute('INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
                     (event_id, TOPIC, _payload(event_id, account_id, delta_cents, balance)))
        conn.commit()
    except BaseException:
        _rollback(conn)
        raise
    return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': balance}


def get_pending(conn):
    rows = conn.execute('SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id').fetchall()
    return [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]


def mark_published(conn, event_id):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError('event_id must be a nonempty string')
    _begin(conn)
    try:
        row = conn.execute('SELECT published FROM outbox WHERE event_id=?', (event_id,)).fetchone()
        if row is None:
            raise ValueError('unknown event_id')
        if row[0] != 1:
            conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
        conn.commit()
    except BaseException:
        _rollback(conn)
        raise
