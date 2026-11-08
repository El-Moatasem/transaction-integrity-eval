import sqlite3


def setup(conn):
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _result(receipt, account_id, amount):
    return {"receipt_id": receipt, "account_id": account_id,
            "amount_cents": amount, "status": "captured"}


def capture(conn, key, account_id, amount_cents):
    if not isinstance(key, str) or not key:
        raise ValueError("invalid key")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("invalid account_id")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError("invalid amount")

    conn.execute("PRAGMA busy_timeout=5000")
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT account_id,amount_cents,receipt_id FROM captures WHERE key=?",
            (key,)).fetchone()
        if row:
            if row[0] != account_id or row[1] != amount_cents:
                raise ValueError("key reused with different parameters")
            conn.rollback()
            return _result(row[2], row[0], row[1])
        acct = conn.execute(
            "SELECT balance_cents FROM accounts WHERE account_id=?",
            (account_id,)).fetchone()
        if acct is None:
            raise ValueError("unknown account")
        if acct[0] < amount_cents:
            raise ValueError("insufficient funds")
        cur = conn.execute(
            "UPDATE accounts SET balance_cents=balance_cents-? WHERE account_id=?",
            (amount_cents, account_id))
        if cur.rowcount != 1:
            raise ValueError("debit failed")
        receipt = "cap_" + key
        conn.execute("INSERT INTO captures(key,account_id,amount_cents,receipt_id) VALUES(?,?,?,?)",
                     (key, account_id, amount_cents, receipt))
        conn.commit()
        return _result(receipt, account_id, amount_cents)
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
