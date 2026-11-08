import json
import sqlite3
from contextlib import contextmanager

TOPIC = 'account.changed'
_BUSY_TIMEOUT_MS = 5000


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


@contextmanager
def _write_txn(conn):
    """Run the body atomically while holding the database write lock.

    Uses BEGIN IMMEDIATE so that read-check-write sequences are serialized
    across processes. If the caller already has a transaction open, a
    savepoint is used instead so that our changes are still all-or-nothing.
    """
    conn.execute('PRAGMA busy_timeout=%d' % _BUSY_TIMEOUT_MS)
    if conn.in_transaction:
        conn.execute('SAVEPOINT apply_event_sp')
        try:
            yield
        except BaseException:
            try:
                conn.execute('ROLLBACK TO SAVEPOINT apply_event_sp')
                conn.execute('RELEASE SAVEPOINT apply_event_sp')
            except sqlite3.Error:
                pass
            raise
        else:
            conn.execute('RELEASE SAVEPOINT apply_event_sp')
        return
    conn.execute('BEGIN IMMEDIATE')
    try:
        yield
        conn.commit()
    except BaseException:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise


def _validate(event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or event_id == '':
        raise ValueError('event_id must be a nonempty string')
    if not isinstance(account_id, str) or account_id == '':
        raise ValueError('account_id must be a nonempty string')
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int):
        raise ValueError('delta_cents must be an int')
    if delta_cents == 0:
        raise ValueError('delta_cents must be nonzero')


def apply_event(conn, event_id, account_id, delta_cents):
    _validate(event_id, account_id, delta_cents)
    with _write_txn(conn):
        row = conn.execute(
            'SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
            (event_id,)).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError('conflicting replay of event %r' % event_id)
            return {'event_id': event_id, 'account_id': account_id,
                    'balance_after_cents': row[2]}

        acct = conn.execute(
            'SELECT balance_cents FROM accounts WHERE account_id=?',
            (account_id,)).fetchone()
        if acct is None:
            raise ValueError('unknown account %r' % account_id)
        balance = acct[0]
        if isinstance(balance, bool) or not isinstance(balance, int):
            raise ValueError('account %r has invalid balance' % account_id)
        new_balance = balance + delta_cents
        if new_balance < 0:
            raise ValueError('resulting balance would be negative')

        cur = conn.execute(
            'UPDATE accounts SET balance_cents=? WHERE account_id=? AND balance_cents=?',
            (new_balance, account_id, balance))
        if cur.rowcount != 1:
            raise sqlite3.DatabaseError('account update affected %d rows' % cur.rowcount)
        conn.execute('INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
                     (event_id, account_id, delta_cents, new_balance))
        payload = json.dumps({'event_id': event_id, 'account_id': account_id,
                              'delta_cents': delta_cents,
                              'balance_after_cents': new_balance},
                             sort_keys=True, separators=(',', ':'))
        conn.execute('INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
                     (event_id, TOPIC, payload))
        return {'event_id': event_id, 'account_id': account_id,
                'balance_after_cents': new_balance}


def get_pending(conn):
    rows = conn.execute(
        'SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id').fetchall()
    return [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]


def mark_published(conn, event_id):
    if not isinstance(event_id, str) or event_id == '':
        raise ValueError('event_id must be a nonempty string')
    with _write_txn(conn):
        row = conn.execute('SELECT published FROM outbox WHERE event_id=?',
                           (event_id,)).fetchone()
        if row is None:
            raise ValueError('unknown outgoing event %r' % event_id)
        if row[0] != 1:
            conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
