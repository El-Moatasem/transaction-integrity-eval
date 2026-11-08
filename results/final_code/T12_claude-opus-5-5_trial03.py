import sqlite3

_MAX_INT = 2**63 - 1
_BUSY_TIMEOUT_MS = 5000


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
    if amount_cents <= 0 or amount_cents > _MAX_INT:
        raise ValueError("amount_cents must be a positive 64-bit integer")


def _apply(conn, capture_id, refund_key, amount_cents):
    existing = conn.execute(
        "SELECT capture_id, amount_cents, receipt_id FROM refunds WHERE refund_key=?",
        (refund_key,)).fetchone()
    if existing is not None:
        if existing[0] != capture_id or existing[1] != amount_cents or isinstance(existing[1], bool):
            raise ValueError("refund_key reused with a different payload")
        return _result(existing[2], existing[0], existing[1]), False

    capture = conn.execute(
        "SELECT account_id, amount_cents FROM captures WHERE capture_id=?",
        (capture_id,)).fetchone()
    if capture is None:
        raise ValueError("missing capture")
    account_id, captured = capture
    if not isinstance(captured, int):
        raise ValueError("invalid captured amount")

    balance = conn.execute(
        "SELECT available_cents FROM balances WHERE account_id=?",
        (account_id,)).fetchone()
    if balance is None:
        raise ValueError("missing balance")
    available = balance[0]
    if not isinstance(available, int):
        raise ValueError("invalid balance")

    rows = conn.execute(
        "SELECT amount_cents FROM refunds WHERE capture_id=?", (capture_id,)).fetchall()
    already = 0
    for (amt,) in rows:
        if isinstance(amt, int):
            already += amt
        else:
            raise ValueError("invalid existing refund")
    if already + amount_cents > captured:
        raise ValueError("refund exceeds captured amount")

    new_available = available + amount_cents
    if new_available > _MAX_INT:
        raise ValueError("balance overflow")

    receipt_id = "ref_" + refund_key
    cur = conn.execute(
        "UPDATE balances SET available_cents=? WHERE account_id=? AND available_cents=?",
        (new_available, account_id, available))
    if cur.rowcount != 1:
        raise sqlite3.DatabaseError("balance update affected unexpected rows")
    conn.execute(
        "INSERT INTO refunds(refund_key, capture_id, amount_cents, receipt_id) VALUES(?,?,?,?)",
        (refund_key, capture_id, amount_cents, receipt_id))
    return _result(receipt_id, capture_id, amount_cents), True


def refund(conn, capture_id: str, refund_key: str, amount_cents: int) -> dict:
    _validate(capture_id, refund_key, amount_cents)
    conn.execute("PRAGMA busy_timeout=%d" % _BUSY_TIMEOUT_MS)

    if conn.in_transaction:
        # Caller already has an open transaction: isolate our work in a savepoint.
        conn.execute("SAVEPOINT refund_sp")
        try:
            result, _ = _apply(conn, capture_id, refund_key, amount_cents)
        except BaseException:
            try:
                conn.execute("ROLLBACK TO SAVEPOINT refund_sp")
                conn.execute("RELEASE SAVEPOINT refund_sp")
            except sqlite3.Error:
                pass
            raise
        conn.execute("RELEASE SAVEPOINT refund_sp")
        return result

    # Take the write lock up front so check-then-write is atomic across processes.
    conn.execute("BEGIN IMMEDIATE")
    try:
        result, _ = _apply(conn, capture_id, refund_key, amount_cents)
        conn.execute("COMMIT")
    except BaseException:
        try:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    return result
