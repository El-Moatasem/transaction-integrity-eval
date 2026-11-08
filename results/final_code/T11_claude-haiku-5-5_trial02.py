import sqlite3

def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _validate(key, account_id, amount_cents):
    if not isinstance(key, str) or key == "":
        raise ValueError("key must be a nonempty string")
    if not isinstance(account_id, str) or account_id == "":
        raise ValueError("account_id must be a nonempty string")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError("amount_cents must be a positive int")


def _rollback(conn):
    try:
        conn.rollback()
    except sqlite3.Error:
        pass


def capture(conn, key, account_id, amount_cents):
    _validate(key, account_id, amount_cents)

    # Finish any transaction the caller left open so we can take the write lock.
    if conn.in_transaction:
        conn.commit()

    # BEGIN IMMEDIATE takes the write lock up front, so concurrent workers are
    # serialized: no racing duplicate inserts, no debit without its receipt.
    # If the database is busy past the connection's timeout, sqlite3.OperationalError
    # propagates with nothing changed.
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT account_id, amount_cents, receipt_id FROM captures WHERE key=?",
            (key,),
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != amount_cents:
                raise ValueError("key already used for a different account or amount")
            conn.commit()
            return {"receipt_id": row[2], "account_id": row[0],
                    "amount_cents": row[1], "status": "captured"}

        acct = conn.execute(
            "SELECT balance_cents FROM accounts WHERE account_id=?",
            (account_id,),
        ).fetchone()
        if acct is None:
            raise ValueError("unknown account")
        if acct[0] < amount_cents:
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
        _rollback(conn)
        raise

    return {"receipt_id": receipt, "account_id": account_id,
            "amount_cents": amount_cents, "status": "captured"}
