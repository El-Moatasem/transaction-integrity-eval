import sqlite3


def setup(conn):
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS accounts("
        "account_id TEXT PRIMARY KEY, balance_cents INTEGER NOT NULL);"
        "CREATE TABLE IF NOT EXISTS captures("
        "key TEXT PRIMARY KEY, account_id TEXT, amount_cents INTEGER, receipt_id TEXT);"
    )
    conn.commit()


def _validate(key, account_id, amount_cents):
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a nonempty string")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id must be a nonempty string")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise ValueError("amount_cents must be an int")
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")


def _rollback_quietly(conn):
    try:
        conn.rollback()
    except sqlite3.Error:
        pass


def capture(conn, key, account_id, amount_cents):
    _validate(key, account_id, amount_cents)

    # Commit anything the caller left pending so BEGIN IMMEDIATE can start.
    if conn.in_transaction:
        conn.commit()

    # BEGIN IMMEDIATE takes the write lock up front. Concurrent callers wait
    # on the connection's busy timeout, so a duplicate request observes the
    # original capture once it commits instead of racing to insert the key.
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT account_id, amount_cents, receipt_id FROM captures WHERE key=?",
            (key,),
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != amount_cents:
                raise ValueError("key already used for a different account or amount")
            conn.rollback()
            return {
                "receipt_id": row[2],
                "account_id": row[0],
                "amount_cents": row[1],
                "status": "captured",
            }

        acc = conn.execute(
            "SELECT balance_cents FROM accounts WHERE account_id=?",
            (account_id,),
        ).fetchone()
        if acc is None:
            raise ValueError("account does not exist")
        if acc[0] < amount_cents:
            raise ValueError("insufficient funds")

        receipt = "cap_" + key
        conn.execute(
            "UPDATE accounts SET balance_cents = balance_cents - ? WHERE account_id=?",
            (amount_cents, account_id),
        )
        conn.execute(
            "INSERT INTO captures(key, account_id, amount_cents, receipt_id) VALUES(?,?,?,?)",
            (key, account_id, amount_cents, receipt),
        )
        conn.commit()
    except BaseException:
        _rollback_quietly(conn)
        raise

    return {
        "receipt_id": receipt,
        "account_id": account_id,
        "amount_cents": amount_cents,
        "status": "captured",
    }
