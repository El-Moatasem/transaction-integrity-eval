import sqlite3

_MAX_INT64 = 2**63 - 1


def setup(conn):
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS accounts(
               account_id TEXT PRIMARY KEY,
               balance_cents INTEGER NOT NULL);
           CREATE TABLE IF NOT EXISTS captures(
               key TEXT PRIMARY KEY,
               account_id TEXT,
               amount_cents INTEGER,
               receipt_id TEXT);"""
    )
    conn.commit()


def _validate(key, account_id, amount_cents):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("key must be a nonempty string")
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("account_id must be a nonempty string")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise ValueError("amount_cents must be an int")
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")


def _result(receipt_id, account_id, amount_cents):
    return {
        "receipt_id": receipt_id,
        "account_id": account_id,
        "amount_cents": amount_cents,
        "status": "captured",
    }


def capture(conn, key: str, account_id: str, amount_cents: int) -> dict:
    _validate(key, account_id, amount_cents)

    # If the caller already has a transaction open, nest via a savepoint so
    # that we never commit or roll back the caller's work; otherwise take a
    # write lock up front (BEGIN IMMEDIATE) so concurrent connections are
    # serialized and the read-check-write sequence is atomic.
    nested = conn.in_transaction
    if nested:
        conn.execute("SAVEPOINT capture_sp")
    else:
        conn.execute("BEGIN IMMEDIATE")

    try:
        row = conn.execute(
            "SELECT account_id, amount_cents, receipt_id FROM captures WHERE key=?",
            (key,),
        ).fetchone()
        if row is not None:
            if row[0] != account_id or row[1] != amount_cents:
                raise ValueError("idempotency key reused with different parameters")
            result = _result(row[2], row[0], row[1])
        else:
            if amount_cents > _MAX_INT64:
                raise ValueError("insufficient funds")
            acct = conn.execute(
                "SELECT balance_cents FROM accounts WHERE account_id=?",
                (account_id,),
            ).fetchone()
            if acct is None:
                raise ValueError("unknown account")
            balance = acct[0]
            if not isinstance(balance, int) or balance < amount_cents:
                raise ValueError("insufficient funds")
            cur = conn.execute(
                "UPDATE accounts SET balance_cents = balance_cents - ? "
                "WHERE account_id=? AND balance_cents >= ?",
                (amount_cents, account_id, amount_cents),
            )
            if cur.rowcount != 1:
                raise ValueError("insufficient funds")
            receipt = "cap_" + key
            conn.execute(
                "INSERT INTO captures(key, account_id, amount_cents, receipt_id) "
                "VALUES (?,?,?,?)",
                (key, account_id, amount_cents, receipt),
            )
            result = _result(receipt, account_id, amount_cents)
    except BaseException:
        try:
            if nested:
                conn.execute("ROLLBACK TO SAVEPOINT capture_sp")
                conn.execute("RELEASE SAVEPOINT capture_sp")
            elif conn.in_transaction:
                conn.rollback()
        except sqlite3.Error:
            pass
        raise

    if nested:
        conn.execute("RELEASE SAVEPOINT capture_sp")
    else:
        try:
            conn.commit()
        except BaseException:
            try:
                if conn.in_transaction:
                    conn.rollback()
            except sqlite3.Error:
                pass
            raise
    return result
