import json

_INT64_MIN = -(2 ** 63)
_INT64_MAX = 2 ** 63 - 1
_SAVEPOINT = "apply_event_sp"


def setup(conn):
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);"
        "CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,"
        "delta_cents INTEGER,balance_after_cents INTEGER);"
        "CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,"
        "published INTEGER);"
    )
    conn.commit()


def _check_event(event_id, account_id, delta_cents):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a nonempty string")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id must be a nonempty string")
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int):
        raise ValueError("delta_cents must be an int")
    if delta_cents == 0:
        raise ValueError("delta_cents must be nonzero")
    if not (_INT64_MIN <= delta_cents <= _INT64_MAX):
        raise ValueError("delta_cents out of range")


def _run(conn, fn):
    """Run fn atomically.

    BEGIN IMMEDIATE takes the write lock up front, so the dedupe check and the
    balance read cannot race with other worker processes. If the caller already
    has a transaction open, a SAVEPOINT is used instead and the caller keeps
    control of the commit.
    """
    nested = conn.in_transaction
    if nested:
        conn.execute(f"SAVEPOINT {_SAVEPOINT}")
    else:
        conn.execute("BEGIN IMMEDIATE")
    try:
        result = fn()
        if nested:
            conn.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
        else:
            conn.commit()
        return result
    except BaseException:
        if nested:
            conn.execute(f"ROLLBACK TO SAVEPOINT {_SAVEPOINT}")
            conn.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
        else:
            conn.rollback()
        raise


def apply_event(conn, event_id, account_id, delta_cents):
    _check_event(event_id, account_id, delta_cents)

    def work():
        dup = conn.execute(
            "SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?",
            (event_id,),
        ).fetchone()
        if dup is not None:
            if dup[0] == account_id and dup[1] == delta_cents:
                return {"event_id": event_id, "account_id": account_id,
                        "balance_after_cents": dup[2]}
            raise ValueError(f"conflicting replay for event_id {event_id!r}")

        row = conn.execute(
            "SELECT balance_cents FROM accounts WHERE account_id=?", (account_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown account_id {account_id!r}")
        new_balance = row[0] + delta_cents
        if new_balance < 0:
            raise ValueError("balance would go negative")
        if not (_INT64_MIN <= new_balance <= _INT64_MAX):
            raise ValueError("balance out of range")

        conn.execute(
            "UPDATE accounts SET balance_cents=? WHERE account_id=?",
            (new_balance, account_id),
        )
        conn.execute(
            "INSERT INTO inbox(event_id,account_id,delta_cents,balance_after_cents) VALUES(?,?,?,?)",
            (event_id, account_id, delta_cents, new_balance),
        )
        payload = json.dumps(
            {"event_id": event_id, "account_id": account_id,
             "delta_cents": delta_cents, "balance_after_cents": new_balance},
            sort_keys=True,
        )
        conn.execute(
            "INSERT INTO outbox(event_id,topic,payload,published) VALUES(?,?,?,0)",
            (event_id, "account.changed", payload),
        )
        return {"event_id": event_id, "account_id": account_id,
                "balance_after_cents": new_balance}

    return _run(conn, work)


def get_pending(conn):
    rows = conn.execute(
        "SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id"
    ).fetchall()
    return [{"event_id": r[0], "topic": r[1], "payload": json.loads(r[2])} for r in rows]


def mark_published(conn, event_id):
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a nonempty string")

    def work():
        row = conn.execute(
            "SELECT published FROM outbox WHERE event_id=?", (event_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown event_id {event_id!r}")
        if row[0] != 1:
            conn.execute("UPDATE outbox SET published=1 WHERE event_id=?", (event_id,))
        return None

    _run(conn, work)
