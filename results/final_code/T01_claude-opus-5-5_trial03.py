import sqlite3

_MAX_INT64 = 2**63 - 1


def setup(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS accounts("
        "account_id TEXT PRIMARY KEY, balance_cents INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS captures("
        "key TEXT PRIMARY KEY, account_id TEXT, amount_cents INTEGER, receipt_id TEXT)"
    )
    conn.commit()


def _validate(key, account_id, amount_cents):
    if not isinstance(key, str) or key == "":
        raise ValueError("key must be a nonempty string")
    if not isinstance(account_id, str) or account_id == "":
        raise ValueError("account_id must be a nonempty string")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise ValueError("amount_cents must be an int")
    if amount_cents <= 0 or amount_cents > _MAX_INT64:
        raise ValueError("amount_cents must be a positive int")


def _result(receipt_id, account_id, amount_cents):
    return {
        "receipt_id": receipt_id,
        "account_id": account_id,
        "amount_cents": amount_cents,
        "status": "captured",
    }


def _do_capture(conn, key, account_id, amount_cents):
    row = conn.execute(
        "SELECT account_id, amount_cents, receipt_id FROM captures WHERE key = ?",
        (key,),
    ).fetchone()
    if row is not None:
        if row[0] != account_id or row[1] != amount_cents:
            raise ValueError("idempotency key reused with different parameters")
        return _result(row[2], row[0], row[1])

    acct = conn.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = ?", (account_id,)
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

    receipt = "cap_" + key
    conn.execute(
        "INSERT INTO captures(key, account_id, amount_cents, receipt_id) "
        "VALUES (?, ?, ?, ?)",
        (key, account_id, amount_cents, receipt),
    )
    return _result(receipt, account_id, amount_cents)


def capture(conn, key: str, account_id: str, amount_cents: int) -> dict:
    _validate(key, account_id, amount_cents)

    if conn.in_transaction:
        # Caller already holds an open transaction: isolate our work in a
        # savepoint so failures leave no partial changes.
        conn.execute("SAVEPOINT capture_sp")
        try:
            result = _do_capture(conn, key, account_id, amount_cents)
        except BaseException:
            try:
                conn.execute("ROLLBACK TO SAVEPOINT capture_sp")
                conn.execute("RELEASE SAVEPOINT capture_sp")
            except sqlite3.Error:
                pass
            raise
        conn.execute("RELEASE SAVEPOINT capture_sp")
        return result

    # Acquire the write lock up front so the idempotency check and the
    # debit/insert are serialized across connections (no lock upgrade races).
    # A busy-timeout here raises sqlite3.OperationalError with no changes.
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _do_capture(conn, key, account_id, amount_cents)
        conn.commit()
    except BaseException:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise
    return result
