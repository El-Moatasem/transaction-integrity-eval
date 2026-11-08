import json
from contextlib import contextmanager

_INT64_MIN = -(2 ** 63)
_INT64_MAX = 2 ** 63 - 1


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


@contextmanager
def _write_tx(conn):
    """Run the enclosed block as one atomic write transaction.

    BEGIN IMMEDIATE takes the database write lock up front, so the dedupe
    check and the balance read are race-free across worker processes. Any
    exception (validation, business rule, or SQLite error) rolls back every
    change made inside the block and is re-raised unchanged.
    """
    old_isolation = conn.isolation_level
    if conn.in_transaction:
        conn.commit()
    conn.isolation_level = None  # manage BEGIN/COMMIT/ROLLBACK explicitly
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            yield
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
    finally:
        conn.isolation_level = old_isolation


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_nonempty_str(value):
    return isinstance(value, str) and len(value) > 0


def apply_event(conn, event_id, account_id, delta_cents):
    if not _is_nonempty_str(event_id):
        raise ValueError('event_id must be a nonempty string')
    if not _is_nonempty_str(account_id):
        raise ValueError('account_id must be a nonempty string')
    if not _is_int(delta_cents) or delta_cents == 0:
        raise ValueError('delta_cents must be a nonzero int')
    if not (_INT64_MIN <= delta_cents <= _INT64_MAX):
        raise ValueError('delta_cents out of range')

    with _write_tx(conn):
        # Dedupe on the inbox.
        recorded = conn.execute(
            'SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
            (event_id,),
        ).fetchone()
        if recorded is not None:
            if recorded[0] != account_id or recorded[1] != delta_cents:
                raise ValueError('event_id replayed with conflicting account/delta')
            return {'event_id': event_id, 'account_id': account_id,
                    'balance_after_cents': recorded[2]}

        row = conn.execute(
            'SELECT balance_cents FROM accounts WHERE account_id=?',
            (account_id,),
        ).fetchone()
        if row is None:
            raise ValueError('unknown account_id')

        new_balance = row[0] + delta_cents
        if new_balance < 0:
            raise ValueError('balance would go negative')
        if not (_INT64_MIN <= new_balance <= _INT64_MAX):
            raise ValueError('balance out of range')

        conn.execute(
            'UPDATE accounts SET balance_cents=? WHERE account_id=?',
            (new_balance, account_id),
        )
        conn.execute(
            'INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
            (event_id, account_id, delta_cents, new_balance),
        )
        payload = json.dumps(
            {'event_id': event_id, 'account_id': account_id,
             'delta_cents': delta_cents, 'balance_after_cents': new_balance},
            sort_keys=True,
        )
        conn.execute(
            'INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
            (event_id, 'account.changed', payload),
        )

    return {'event_id': event_id, 'account_id': account_id,
            'balance_after_cents': new_balance}


def get_pending(conn):
    rows = conn.execute(
        'SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id'
    ).fetchall()
    return [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]


def mark_published(conn, event_id):
    with _write_tx(conn):
        row = conn.execute(
            'SELECT 1 FROM outbox WHERE event_id=?', (event_id,)
        ).fetchone()
        if row is None:
            raise ValueError('unknown event_id')
        conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
