import json
import sqlite3
from contextlib import contextmanager

TOPIC = 'account.changed'
_MAX_BUSY_MS = 5000


def setup(conn):
    with _txn(conn):
        conn.execute('CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER)')
        conn.execute('CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,'
                     'delta_cents INTEGER,balance_after_cents INTEGER)')
        conn.execute('CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,'
                     'payload TEXT,published INTEGER)')


def _bound_busy_timeout(conn):
    # Never block indefinitely waiting for a lock; keep a finite busy timeout.
    try:
        cur = conn.execute('PRAGMA busy_timeout').fetchone()[0]
        if cur is None or cur <= 0 or cur > _MAX_BUSY_MS:
            conn.execute('PRAGMA busy_timeout=%d' % _MAX_BUSY_MS)
    except sqlite3.Error:
        pass


@contextmanager
def _txn(conn):
    """Run the body atomically: everything commits or nothing persists."""
    _bound_busy_timeout(conn)
    if not conn.in_transaction:
        conn.execute('BEGIN IMMEDIATE')
        try:
            yield
        except BaseException:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise
        conn.commit()
    else:
        # A transaction is already open (e.g. autocommit=False connections):
        # isolate this call's changes in a savepoint.
        conn.execute('SAVEPOINT svc_txn')
        try:
            yield
        except BaseException:
            try:
                conn.execute('ROLLBACK TO svc_txn')
                conn.execute('RELEASE svc_txn')
            except sqlite3.Error:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            raise
        conn.execute('RELEASE svc_txn')
        conn.commit()


def _validate(event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError('event_id must be a nonempty string')
    if not isinstance(account_id, str) or not account_id:
        raise ValueError('account_id must be a nonempty string')
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int) or delta_cents == 0:
        raise ValueError('delta_cents must be a nonzero int')
    if not (-(2 ** 63) <= delta_cents < 2 ** 63):
        raise ValueError('delta_cents out of range')


def apply_event(conn, event_id, account_id, delta_cents):
    _validate(event_id, account_id, delta_cents)
    with _txn(conn):
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
            raise ValueError('account %r has invalid balance' % account_id)
        new_balance = balance + delta_cents
        if new_balance < 0:
            raise ValueError('insufficient funds')
        if new_balance >= 2 ** 63:
            raise ValueError('balance overflow')
        cur = conn.execute('UPDATE accounts SET balance_cents=? WHERE account_id=? AND balance_cents=?',
                           (new_balance, account_id, balance))
        if cur.rowcount != 1:
            raise sqlite3.DatabaseError('account update affected %d rows' % cur.rowcount)
        conn.execute('INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
                     (event_id, account_id, delta_cents, new_balance))
        payload = json.dumps({'event_id': event_id, 'account_id': account_id,
                              'delta_cents': delta_cents, 'balance_after_cents': new_balance},
                             sort_keys=True)
        conn.execute('INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
                     (event_id, TOPIC, payload))
    return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': new_balance}


def get_pending(conn):
    rows = conn.execute('SELECT event_id,topic,payload FROM outbox WHERE published=0').fetchall()
    out = [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]
    out.sort(key=lambda d: d['event_id'])
    return out


def mark_published(conn, event_id):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError('event_id must be a nonempty string')
    with _txn(conn):
        row = conn.execute('SELECT published FROM outbox WHERE event_id=?', (event_id,)).fetchone()
        if row is None:
            raise ValueError('unknown event %r' % event_id)
        if row[0] != 1:
            conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
