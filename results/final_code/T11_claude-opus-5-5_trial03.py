import sqlite3

_MAX_INT64 = 2**63 - 1
_BUSY_TIMEOUT_MS = 5000


def setup(conn):
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS captures(key TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER,receipt_id TEXT);"""
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
    if (
        isinstance(amount_cents, bool)
        or not isinstance(amount_cents, int)
        or amount_cents <= 0
        or amount_cents > _MAX_INT64
    ):
        raise ValueError("amount_cents must be a positive int")


def capture(conn, key: str, account_id: str, amount_cents: int) -> dict:
    _validate(key, account_id, amount_cents)
    amount_cents = int(amount_cents)

    # Bounded wait for locks held by other workers; never block indefinitely.
    conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")

    # Finish any implicit transaction left open by the caller so that we can
    # start our own write transaction.
    if conn.in_transaction:
        conn.commit()

    old_isolation = conn.isolation_level
    conn.isolation_level = None  # manual transaction control
    try:
        # Take the write lock up front so check-then-act is atomic across processes.
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT account_id, amount_cents, receipt_id FROM captures WHERE key = ?",
                (key,),
            ).fetchone()
            if row is not None:
                stored_account, stored_amount, stored_receipt = row
                if stored_account != account_id or stored_amount != amount_cents:
                    raise ValueError("idempotency key reused with different parameters")
                conn.execute("ROLLBACK")
                return _result(stored_receipt, stored_account, stored_amount)

            acct = conn.execute(
                "SELECT balance_cents FROM accounts WHERE account_id = ?",
                (account_id,),
            ).fetchone()
            if acct is None:
                raise ValueError("account does not exist")
            if acct[0] < amount_cents:
                raise ValueError("insufficient funds")

            cur = conn.execute(
                "UPDATE accounts SET balance_cents = balance_cents - ? "
                "WHERE account_id = ? AND balance_cents >= ?",
                (amount_cents, account_id, amount_cents),
            )
            if cur.rowcount != 1:
                raise ValueError("insufficient funds")

            receipt_id = "cap_" + key
            conn.execute(
                "INSERT INTO captures(key, account_id, amount_cents, receipt_id) VALUES (?, ?, ?, ?)",
                (key, account_id, amount_cents, receipt_id),
            )
            conn.execute("COMMIT")
            return _result(receipt_id, account_id, amount_cents)
        except BaseException:
            if conn.in_transaction:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise
    finally:
        conn.isolation_level = old_isolation
