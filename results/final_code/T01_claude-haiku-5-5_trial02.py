import sqlite3


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
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


def capture(conn, key, account_id, amount_cents):
    _validate(key, account_id, amount_cents)

    # Use explicit transactions only. Commit anything the caller left open,
    # as the original implementation did on every capture.
    if conn.in_transaction:
        conn.commit()
    saved_isolation = conn.isolation_level
    conn.isolation_level = None  # disable implicit sqlite3 transaction handling
    try:
        # BEGIN IMMEDIATE takes the write lock up front, so concurrent captures
        # on other connections are serialized. A waiting caller honours the
        # connection's busy timeout and raises sqlite3.OperationalError on timeout.
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT account_id, amount_cents, receipt_id FROM captures WHERE key=?",
                (key,),
            ).fetchone()
            if row is not None:
                stored_account, stored_amount, stored_receipt = row
                if stored_account != account_id or stored_amount != amount_cents:
                    raise ValueError("key already used with a different account or amount")
                conn.execute("COMMIT")
                return {
                    "receipt_id": stored_receipt,
                    "account_id": stored_account,
                    "amount_cents": stored_amount,
                    "status": "captured",
                }

            acct = conn.execute(
                "SELECT balance_cents FROM accounts WHERE account_id=?",
                (account_id,),
            ).fetchone()
            if acct is None:
                raise ValueError("account does not exist")
            if acct[0] < amount_cents:
                raise ValueError("insufficient funds")

            cur = conn.execute(
                "UPDATE accounts SET balance_cents=balance_cents-? "
                "WHERE account_id=? AND balance_cents>=?",
                (amount_cents, account_id, amount_cents),
            )
            if cur.rowcount != 1:
                raise ValueError("insufficient funds")

            receipt = "cap_" + key
            conn.execute(
                "INSERT INTO captures(key, account_id, amount_cents, receipt_id) VALUES(?,?,?,?)",
                (key, account_id, amount_cents, receipt),
            )
            conn.execute("COMMIT")
            return {
                "receipt_id": receipt,
                "account_id": account_id,
                "amount_cents": amount_cents,
                "status": "captured",
            }
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.isolation_level = saved_isolation
