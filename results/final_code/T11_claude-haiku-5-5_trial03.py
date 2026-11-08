import sqlite3


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _validate(key, account_id, amount_cents):
    if not isinstance(key, str) or len(key) == 0:
        raise ValueError("key must be a nonempty string")
    if not isinstance(account_id, str) or len(account_id) == 0:
        raise ValueError("account_id must be a nonempty string")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise ValueError("amount_cents must be an int")
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")


def _receipt(row):
    return {"receipt_id": row[2], "account_id": row[0], "amount_cents": row[1], "status": "captured"}


def capture(conn, key, account_id, amount_cents):
    _validate(key, account_id, amount_cents)

    # Commit any pending work the caller left open so we can take the write lock.
    if conn.in_transaction:
        conn.commit()

    # BEGIN IMMEDIATE takes the write lock up front, so the existence check,
    # balance check, debit and receipt insert are atomic across processes.
    # It waits at most the connection's busy timeout, then raises
    # sqlite3.OperationalError with nothing changed.
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            'SELECT account_id,amount_cents,receipt_id FROM captures WHERE key=?', (key,)
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != amount_cents:
                raise ValueError("key already used for a different account or amount")
            result = _receipt(row)
        else:
            bal = conn.execute(
                'SELECT balance_cents FROM accounts WHERE account_id=?', (account_id,)
            ).fetchone()
            if bal is None:
                raise ValueError("account does not exist")
            if bal[0] < amount_cents:
                raise ValueError("insufficient funds")
            receipt = 'cap_' + key
            conn.execute(
                'UPDATE accounts SET balance_cents=balance_cents-? WHERE account_id=?',
                (amount_cents, account_id),
            )
            conn.execute(
                'INSERT INTO captures(key,account_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
                (key, account_id, amount_cents, receipt),
            )
            result = {"receipt_id": receipt, "account_id": account_id,
                      "amount_cents": amount_cents, "status": "captured"}
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return result
