import sqlite3

_BUSY_TIMEOUT_MS = 5000


def setup(conn):
    if conn.in_transaction:
        conn.commit()
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY, balance_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY, account_id TEXT, amount_cents INTEGER, receipt_id TEXT);"""
    )
    conn.commit()


def _result(receipt_id, account_id, amount_cents):
    return {
        "receipt_id": receipt_id,
        "account_id": account_id,
        "amount_cents": amount_cents,
        "status": "captured",
    }


def _validate(key, account_id, amount_cents):
    if not isinstance(key, str) or key == "":
        raise ValueError("key must be a nonempty string")
    if not isinstance(account_id, str) or account_id == "":
        raise ValueError("account_id must be a nonempty string")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise ValueError("amount_cents must be an int")
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")


def _do_capture(conn, key, account_id, amount_cents):
    row = conn.execute(
        "SELECT account_id, amount_cents, receipt_id FROM captures WHERE key=?",
        (key,),
    ).fetchone()
    if row is not None:
        if row[0] != account_id or row[1] != amount_cents:
            raise ValueError("key already used for a different payment")
        return _result(row[2], row[0], row[1])

    acct = conn.execute(
        "SELECT balance_cents FROM accounts WHERE account_id=?", (account_id,)
    ).fetchone()
    if acct is None:
        raise ValueError("unknown account")
    if acct[0] < amount_cents:
        raise ValueError("insufficient funds")

    receipt = "cap_" + key
    cur = conn.execute(
        "UPDATE accounts SET balance_cents = balance_cents - ? "
        "WHERE account_id=? AND balance_cents >= ?",
        (amount_cents, account_id, amount_cents),
    )
    if cur.rowcount != 1:
        raise ValueError("insufficient funds")
    conn.execute(
        "INSERT INTO captures(key, account_id, amount_cents, receipt_id) VALUES(?,?,?,?)",
        (key, account_id, amount_cents, receipt),
    )
    return _result(receipt, account_id, amount_cents)


def capture(conn, key: str, account_id: str, amount_cents: int) -> dict:
    _validate(key, account_id, amount_cents)

    # Bound lock waits so calls never block indefinitely.
    conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")

    own_txn = not conn.in_transaction
    if own_txn:
        # Take the write lock up front so check-then-act is serialized
        # across processes.
        conn.execute("BEGIN IMMEDIATE")
    else:
        conn.execute("SAVEPOINT capture_sp")

    try:
        result = _do_capture(conn, key, account_id, amount_cents)
    except BaseException:
        try:
            if own_txn:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
            else:
                conn.execute("ROLLBACK TO capture_sp")
                conn.execute("RELEASE capture_sp")
        except sqlite3.Error:
            pass
        raise

    try:
        if own_txn:
            conn.execute("COMMIT")
        else:
            conn.execute("RELEASE capture_sp")
    except BaseException:
        try:
            if own_txn:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
            else:
                conn.execute("ROLLBACK TO capture_sp")
                conn.execute("RELEASE capture_sp")
        except sqlite3.Error:
            pass
        raise
    return result
