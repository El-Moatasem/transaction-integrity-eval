import json
import sqlite3
from contextlib import contextmanager

_INT64_MIN = -(2 ** 63)
_INT64_MAX = 2 ** 63 - 1


def setup(conn):
    with _write_tx(conn):
        conn.execute("CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER)")


@contextmanager
def _write_tx(conn):
    """Run the body as one atomic write transaction.

    BEGIN IMMEDIATE takes the write lock up front, so the read-check-write
    sequence cannot interleave with another worker's. Any exception rolls
    back everything the body did. Pending work on the connection is committed
    first, matching the behaviour of the previous implementation.
    """
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise


def _check_id(name, value):
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{name} must be a nonempty string")


def apply_event(conn, event_id, account_id, delta_cents):
    _check_id("event_id", event_id)
    _check_id("account_id", account_id)
    if isinstance(delta_cents, bool) or not isinstance(delta_cents, int):
        raise ValueError("delta_cents must be an int")
    if delta_cents == 0:
        raise ValueError("delta_cents must be nonzero")
    if not (_INT64_MIN <= delta_cents <= _INT64_MAX):
        raise ValueError("delta_cents out of range")

    with _write_tx(conn):
        row = conn.execute(
            "SELECT account_id, delta_cents, balance_after_cents FROM inbox WHERE event_id=?",
            (event_id,),
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != delta_cents:
                raise ValueError(f"event {event_id!r} replayed with conflicting content")
            return {"event_id": event_id, "account_id": account_id, "balance_after_cents": row[2]}

        row = conn.execute(
            "SELECT balance_cents FROM accounts WHERE account_id=?", (account_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown account {account_id!r}")
        new_balance = row[0] + delta_cents
        if not (_INT64_MIN <= new_balance <= _INT64_MAX):
            raise ValueError("resulting balance out of range")
        if new_balance < 0:
            raise ValueError("resulting balance would be negative")

        cur = conn.execute(
            "UPDATE accounts SET balance_cents=? WHERE account_id=?", (new_balance, account_id)
        )
        if cur.rowcount != 1:
            raise sqlite3.DatabaseError("account update did not affect exactly one row")
        conn.execute(
            "INSERT INTO inbox(event_id, account_id, delta_cents, balance_after_cents) VALUES(?,?,?,?)",
            (event_id, account_id, delta_cents, new_balance),
        )
        payload = json.dumps(
            {
                "event_id": event_id,
                "account_id": account_id,
                "delta_cents": delta_cents,
                "balance_after_cents": new_balance,
            },
            sort_keys=True,
        )
        conn.execute(
            "INSERT INTO outbox(event_id, topic, payload, published) VALUES(?,?,?,0)",
            (event_id, "account.changed", payload),
        )
    return {"event_id": event_id, "account_id": account_id, "balance_after_cents": new_balance}


def get_pending(conn):
    rows = conn.execute(
        "SELECT event_id, topic, payload FROM outbox WHERE published=0 ORDER BY event_id"
    ).fetchall()
    return [
        {"event_id": event_id, "topic": topic, "payload": json.loads(payload)}
        for event_id, topic, payload in rows
    ]


def mark_published(conn, event_id):
    _check_id("event_id", event_id)
    with _write_tx(conn):
        cur = conn.execute("UPDATE outbox SET published=1 WHERE event_id=?", (event_id,))
        if cur.rowcount == 0:
            raise ValueError(f"unknown outbox event {event_id!r}")
