import json


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""")
    conn.commit()


def _validate(event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a nonempty string")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id must be a nonempty string")
    if type(delta_cents) is not int:
        raise ValueError("delta_cents must be an int (bool is not allowed)")
    if delta_cents == 0:
        raise ValueError("delta_cents must be nonzero")


def apply_event(conn, event_id, account_id, delta_cents):
    _validate(event_id, account_id, delta_cents)

    # Use one write transaction. BEGIN IMMEDIATE takes the write lock up front,
    # so the dedupe check and the balance change cannot interleave with another
    # writer. If the caller already has a transaction open, use a savepoint
    # instead so the work still rolls back as a unit.
    own_tx = not conn.in_transaction
    if own_tx:
        conn.execute("BEGIN IMMEDIATE")
    else:
        conn.execute("SAVEPOINT apply_event")
    try:
        row = conn.execute(
            'SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',
            (event_id,),
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError(f"conflicting replay for event_id {event_id!r}")
            result = {'event_id': event_id, 'account_id': account_id,
                      'balance_after_cents': int(row[2])}
            _finish(conn, own_tx, commit=True)
            return result

        acct = conn.execute(
            'SELECT balance_cents FROM accounts WHERE account_id=?', (account_id,)
        ).fetchone()
        if acct is None:
            raise ValueError(f"unknown account_id {account_id!r}")
        new_balance = acct[0] + delta_cents
        if new_balance < 0:
            raise ValueError("insufficient funds: resulting balance would be negative")

        conn.execute('UPDATE accounts SET balance_cents=? WHERE account_id=?',
                     (new_balance, account_id))
        conn.execute('INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)',
                     (event_id, account_id, delta_cents, new_balance))
        payload = json.dumps({'event_id': event_id, 'account_id': account_id,
                              'delta_cents': delta_cents,
                              'balance_after_cents': new_balance},
                             sort_keys=True)
        conn.execute('INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)',
                     (event_id, 'account.changed', payload))
        _finish(conn, own_tx, commit=True)
        return {'event_id': event_id, 'account_id': account_id,
                'balance_after_cents': new_balance}
    except BaseException:
        _finish(conn, own_tx, commit=False)
        raise


def _finish(conn, own_tx, commit):
    if own_tx:
        conn.execute("COMMIT" if commit else "ROLLBACK")
    elif commit:
        conn.execute("RELEASE apply_event")
    else:
        conn.execute("ROLLBACK TO apply_event")
        conn.execute("RELEASE apply_event")


def get_pending(conn):
    rows = conn.execute(
        'SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id'
    ).fetchall()
    return [{'event_id': r[0], 'topic': r[1], 'payload': json.loads(r[2])} for r in rows]


def mark_published(conn, event_id):
    cur = conn.execute('UPDATE outbox SET published=1 WHERE event_id=?', (event_id,))
    if cur.rowcount == 0:
        conn.rollback()
        raise ValueError(f"unknown event_id {event_id!r}")
    conn.commit()
