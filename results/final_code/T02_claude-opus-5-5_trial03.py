import sqlite3


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS captures(capture_id TEXT PRIMARY KEY,account_id TEXT,amount_cents INTEGER);
    CREATE TABLE IF NOT EXISTS balances(account_id TEXT PRIMARY KEY,available_cents INTEGER);
    CREATE TABLE IF NOT EXISTS refunds(refund_key TEXT PRIMARY KEY,capture_id TEXT,amount_cents INTEGER,receipt_id TEXT);""")
    conn.commit()


def _result(receipt_id, capture_id, amount_cents):
    return {"receipt_id": receipt_id, "capture_id": capture_id,
            "amount_cents": amount_cents, "status": "refunded"}


def _validate(capture_id, refund_key, amount_cents):
    if not isinstance(capture_id, str) or not capture_id:
        raise ValueError("capture_id must be a nonempty string")
    if not isinstance(refund_key, str) or not refund_key:
        raise ValueError("refund_key must be a nonempty string")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise ValueError("amount_cents must be an integer")
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")


def _do_refund(conn, capture_id, refund_key, amount_cents):
    existing = conn.execute(
        "SELECT capture_id,amount_cents,receipt_id FROM refunds WHERE refund_key=?",
        (refund_key,)).fetchone()
    if existing is not None:
        if existing[0] != capture_id or existing[1] != amount_cents:
            raise ValueError("refund_key reused with different payload")
        return _result(existing[2], existing[0], existing[1])

    capture = conn.execute(
        "SELECT account_id,amount_cents FROM captures WHERE capture_id=?",
        (capture_id,)).fetchone()
    if capture is None:
        raise ValueError("missing capture")
    account_id, captured = capture
    if isinstance(captured, bool) or not isinstance(captured, int):
        raise ValueError("invalid captured amount")

    balance = conn.execute(
        "SELECT available_cents FROM balances WHERE account_id=?",
        (account_id,)).fetchone()
    if balance is None:
        raise ValueError("missing balance")

    already = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) FROM refunds WHERE capture_id=?",
        (capture_id,)).fetchone()[0]
    if already + amount_cents > captured:
        raise ValueError("refund exceeds captured amount")

    cur = conn.execute(
        "UPDATE balances SET available_cents=available_cents+? WHERE account_id=?",
        (amount_cents, account_id))
    if cur.rowcount != 1:
        raise ValueError("missing balance")
    receipt_id = "ref_" + refund_key
    conn.execute(
        "INSERT INTO refunds(refund_key,capture_id,amount_cents,receipt_id) VALUES(?,?,?,?)",
        (refund_key, capture_id, amount_cents, receipt_id))
    return _result(receipt_id, capture_id, amount_cents)


def refund(conn, capture_id, refund_key, amount_cents):
    _validate(capture_id, refund_key, amount_cents)

    autocommit = getattr(conn, "autocommit", None)
    legacy = autocommit is None or autocommit == getattr(
        sqlite3, "LEGACY_TRANSACTION_CONTROL", -1)

    if autocommit is False:
        # A transaction is always implicitly open; start a fresh one and take
        # the write lock immediately with a no-op write.
        conn.commit()
        try:
            conn.execute("UPDATE balances SET available_cents=available_cents WHERE 0")
            result = _do_refund(conn, capture_id, refund_key, amount_cents)
            conn.commit()
            return result
        except BaseException:
            conn.rollback()
            raise

    saved_iso = conn.isolation_level if legacy else None
    if conn.in_transaction:
        conn.commit()
    try:
        if legacy:
            conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            result = _do_refund(conn, capture_id, refund_key, amount_cents)
            conn.execute("COMMIT")
            return result
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        if legacy:
            conn.isolation_level = saved_iso
