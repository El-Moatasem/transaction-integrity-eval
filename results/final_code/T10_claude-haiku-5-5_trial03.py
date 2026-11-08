import json
import sqlite3


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


def _begin_write(conn):
    # BEGIN IMMEDIATE takes the write lock up front, so the read-check-write
    # sequence below cannot interleave with another writer. Any pending
    # implicit transaction is committed first so BEGIN can start cleanly.
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")


def _validate_event(event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a nonempty string")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id must be a nonempty string")
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int):
        raise ValueError("delta_cents must be an int")
    if delta_cents == 0:
        raise ValueError("delta_cents must be nonzero")


def apply_event(conn, event_id, account_id, delta_cents):
    _validate_event(event_id, account_id, delta_cents)
    _begin_write(conn)
    try:
        # Inbox dedupe: a previously applied event is replayed, not reapplied.
        row = conn.execute(
            'SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
            (event_id,),
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError(f"event_id {event_id!r} already applied with different content")
            conn.rollback()
            return {'event_id': event_id, 'account_id': account_id, 'balance_after_cents': row[2]}

        acct = conn.execute(
            'SELECT balance_cents FROM accounts WHERE account_id=?',
            (account_id,),
        ).fetchone()
        if acct is None:
            raise ValueError(f"unknown account {account_id!r}")
        new_balance = acct[0] + delta_cents
        if new_balance < 0:
            raise ValueError("insufficient balance: resulting balance would be negative")

        cur = conn.execute(
            'UPDATE accounts SET balance_cents=? WHERE account_id=?',
            (new_balance, account_id),
        )
        if cur.rowcount != 1:
            raise sqlite3.DatabaseError("account update affected no rows")
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
        conn.commit()
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
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
    _begin_write(conn)
    try:
        cur = conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
        if cur.rowcount == 0:
            raise ValueError(f"unknown outbox event_id {event_id!r}")
        conn.commit()
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
