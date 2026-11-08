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


class _Tx:
    """Atomic write transaction. Uses BEGIN IMMEDIATE so the write lock is taken
    up front (no read->write upgrade races between workers); falls back to a
    savepoint if the connection already has an open transaction."""

    _counter = 0

    def __init__(self, conn):
        self.conn = conn
        self.savepoint = None

    def __enter__(self):
        if self.conn.in_transaction:
            _Tx._counter += 1
            self.savepoint = 'svc_tx_%d' % _Tx._counter
            self.conn.execute('SAVEPOINT ' + self.savepoint)
        else:
            self.conn.execute('BEGIN IMMEDIATE')
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            try:
                if self.savepoint:
                    self.conn.execute('RELEASE SAVEPOINT ' + self.savepoint)
                    self.conn.commit()
                else:
                    self.conn.execute('COMMIT')
            except BaseException:
                self._rollback()
                raise
        else:
            self._rollback()
        return False

    def _rollback(self):
        try:
            if self.savepoint:
                self.conn.execute('ROLLBACK TO SAVEPOINT ' + self.savepoint)
                self.conn.execute('RELEASE SAVEPOINT ' + self.savepoint)
            elif self.conn.in_transaction:
                self.conn.execute('ROLLBACK')
        except sqlite3.Error:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass


def _validate(event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError('event_id must be a nonempty string')
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError('account_id must be a nonempty string')
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int):
        raise ValueError('delta_cents must be an int')
    if delta_cents == 0:
        raise ValueError('delta_cents must be nonzero')
    if not (_INT64_MIN <= delta_cents <= _INT64_MAX):
        raise ValueError('delta_cents out of range')


def _payload(event_id, account_id, delta_cents, balance_after):
    return json.dumps({'event_id': event_id, 'account_id': account_id,
                       'delta_cents': delta_cents, 'balance_after_cents': balance_after},
                      sort_keys=True, separators=(',', ':'))


def apply_event(conn, event_id, account_id, delta_cents):
    _validate(event_id, account_id, delta_cents)
    with _Tx(conn):
        row = conn.execute('SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
                           (event_id,)).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError('conflicting replay of event %r' % event_id)
            return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': row[2]}
        acc = conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?', (account_id,)).fetchone()
        if acc is None:
            raise ValueError('unknown account %r' % account_id)
        balance = acc[0]
        if isinstance(balance, bool) or not isinstance(balance, int):
            raise ValueError('account %r has an invalid balance' % account_id)
        new_balance = balance + delta_cents
        if new_balance < 0:
            raise ValueError('balance would go negative')
        if new_balance > _INT64_MAX:
            raise ValueError('balance overflow')
        cur = conn.execute('UPDATE accounts SET balance_cents=? WHERE account_id=? AND balance_cents=?',
                           (new_balance, account_id, balance))
        if cur.rowcount != 1:
            raise sqlite3.OperationalError('account balance changed concurrently')
        conn.execute('INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
                     (event_id, account_id, delta_cents, new_balance))
        conn.execute('INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
                     (event_id, TOPIC, _payload(event_id, account_id, delta_cents, new_balance)))
    return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': new_balance}


def get_pending(conn):
    rows = conn.execute('SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id').fetchall()
    result = [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]
    result.sort(key=lambda d: d['event_id'])
    return result


def mark_published(conn, event_id):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError('event_id must be a nonempty string')
    with _Tx(conn):
        row = conn.execute('SELECT published FROM outbox WHERE event_id=?', (event_id,)).fetchone()
        if row is None:
            raise ValueError('unknown event %r' % event_id)
        if row[0] != 1:
            conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
