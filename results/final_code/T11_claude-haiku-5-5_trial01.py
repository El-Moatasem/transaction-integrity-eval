import sqlite3

def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()

def capture(conn, key, account_id, amount_cents):
    # Input validation happens before any database access, so invalid input never changes anything.
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a nonempty string")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id must be a nonempty string")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError("amount_cents must be a positive int")

    # Commit any pending work of the caller (matches the previous behaviour), then take the
    # write lock up front so concurrent workers serialize on the check-and-debit step.
    # BEGIN IMMEDIATE waits up to the connection's busy timeout and then raises
    # sqlite3.OperationalError with no changes made.
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            'SELECT account_id,amount_cents,receipt_id FROM captures WHERE key=?', (key,)
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != amount_cents:
                raise ValueError("key already used with a different account or amount")
            result = {"receipt_id": row[2], "account_id": row[0],
                      "amount_cents": row[1], "status": "captured"}
        else:
            acct = conn.execute(
                'SELECT balance_cents FROM accounts WHERE account_id=?', (account_id,)
            ).fetchone()
            if acct is None:
                raise ValueError("unknown account")
            if acct[0] < amount_cents:
                raise ValueError("insufficient funds")
            receipt = 'cap_' + key
            cur = conn.execute(
                'UPDATE accounts SET balance_cents=balance_cents-? WHERE account_id=?',
                (amount_cents, account_id))
            if cur.rowcount != 1:
                raise sqlite3.DatabaseError("unexpected row count on account debit")
            conn.execute(
                'INSERT INTO captures(key,account_id,amount_cents,receipt_id) VALUES(?,?,?,?)',
                (key, account_id, amount_cents, receipt))
            result = {"receipt_id": receipt, "account_id": account_id,
                      "amount_cents": amount_cents, "status": "captured"}
        conn.commit()
        return result
    except BaseException:
        # Any failure (validation conflict, insufficient funds, SQLite error, trigger failure)
        # rolls back the whole transaction so debit and receipt are never separated.
        conn.rollback()
        raise
