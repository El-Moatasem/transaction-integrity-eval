import json

_TOPIC = 'account.changed'


def _begin(conn):
    try:
        conn.execute('PRAGMA busy_timeout=5000')
    except Exception:
        pass
    if conn.in_transaction:
        conn.commit()
    conn.execute('BEGIN IMMEDIATE')


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


def apply_event(conn, event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError('invalid event_id')
    if not isinstance(account_id, str) or not account_id:
        raise ValueError('invalid account_id')
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int) or delta_cents == 0:
        raise ValueError('invalid delta_cents')
    _begin(conn)
    try:
        row = conn.execute('SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
                           (event_id,)).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError('conflicting replay')
            result = {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': row[2]}
            conn.commit()
            return result
        acct = conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?', (account_id,)).fetchone()
        if acct is None:
            raise ValueError('unknown account')
        balance = acct[0] + delta_cents
        if balance < 0:
            raise ValueError('insufficient funds')
        conn.execute('UPDATE accounts SET balance_cents=? WHERE account_id=?', (balance, account_id))
        conn.execute('INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
                     (event_id, account_id, delta_cents, balance))
        payload = json.dumps({'event_id': event_id, 'account_id': account_id,
                              'delta_cents': delta_cents, 'balance_after_cents': balance},
                             sort_keys=True, separators=(',', ':'))
        conn.execute('INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
                     (event_id, _TOPIC, payload))
        conn.commit()
        return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': balance}
    except BaseException:
        conn.rollback()
        raise


def get_pending(conn):
    rows = conn.execute('SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id').fetchall()
    return [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]


def mark_published(conn, event_id):
    _begin(conn)
    try:
        cur = conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
        if cur.rowcount == 0:
            raise ValueError('unknown event_id')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
