import json
import sqlite3
from contextlib import contextmanager


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


@contextmanager
def _write_tx(conn):
    """One explicit SQLite write transaction.

    BEGIN IMMEDIATE takes the database write lock up front, so the inbox
    dedupe check and the subsequent writes cannot interleave with another
    connection. Any exception rolls back everything done inside the block.
    """
    if conn.in_transaction:
        conn.commit()
    old_isolation = conn.isolation_level
    conn.isolation_level = None  # manage BEGIN/COMMIT/ROLLBACK explicitly
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        try:
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.isolation_level = old_isolation


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def apply_event(conn, event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a nonempty string")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id must be a nonempty string")
    if not _is_int(delta_cents) or delta_cents == 0:
        raise ValueError("delta_cents must be a nonzero int")

    with _write_tx(conn):
        # Inbox dedupe: a replay must not change anything.
        row = conn.execute(
            'SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
            (event_id,),
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError(f"conflicting replay for event_id {event_id!r}")
            return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': row[2]}

        acct = conn.execute(
            'SELECT balance_cents FROM accounts WHERE account_id=?',
            (account_id,),
        ).fetchone()
        if acct is None:
            raise ValueError(f"unknown account_id {account_id!r}")

        new_balance = acct[0] + delta_cents
        if new_balance < 0:
            raise ValueError("insufficient funds: resulting balance would be negative")

        conn.execute(
            'UPDATE accounts SET balance_cents=? WHERE account_id=?',
            (new_balance, account_id),
        )
        conn.execute(
            'INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
            (event_id, account_id, delta_cents, new_balance),
        )
        payload = json.dumps(
            {
                'event_id': event_id,
                'account_id': account_id,
                'delta_cents': delta_cents,
                'balance_after_cents': new_balance,
            },
            sort_keys=True,
        )
        conn.execute(
            'INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
            (event_id, 'account.changed', payload),
        )

    return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': new_balance}


def get_pending(conn):
    rows = conn.execute(
        'SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id'
    ).fetchall()
    return [
        {'event_id': event_id, 'topic': topic, 'payload': json.loads(payload)}
        for event_id, topic, payload in rows
    ]


def mark_published(conn, event_id):
    with _write_tx(conn):
        row = conn.execute(
            'SELECT published FROM outbox WHERE event_id=?',
            (event_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown outbox event_id {event_id!r}")
        if row[0] != 1:
            conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
