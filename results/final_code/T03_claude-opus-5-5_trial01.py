import re
import sqlite3

SUPPORTED_CURRENCIES = {"USD": 2, "EUR": 2}
_AMOUNT_RE = re.compile(r"(\d+)(?:\.(\d+))?", re.ASCII)


def setup(conn):
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));"""
    )
    conn.commit()


def _parse_amount(amount, currency):
    if not isinstance(amount, str):
        raise ValueError("amount must be a decimal string")
    m = _AMOUNT_RE.fullmatch(amount)
    if not m:
        raise ValueError("invalid amount format")
    places = SUPPORTED_CURRENCIES[currency]
    whole, frac = m.group(1), m.group(2) or ""
    significant = frac.rstrip("0")
    if len(significant) > places:
        raise ValueError("too many fractional digits")
    minor = int(whole) * 10**places + int(significant.ljust(places, "0") or "0")
    if minor <= 0:
        raise ValueError("amount must be greater than zero")
    return minor


def _validate(transfer_id, source, target, amount, currency):
    for name, val in (("transfer_id", transfer_id), ("source", source),
                      ("target", target), ("currency", currency)):
        if not isinstance(val, str) or not val:
            raise ValueError(f"{name} must be a non-empty string")
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError("unsupported currency")
    if source == target:
        raise ValueError("source and target must differ")
    return _parse_amount(amount, currency)


def post_transfer(conn, transfer_id, source, target, amount, currency):
    minor = _validate(transfer_id, source, target, amount, currency)

    outer = not conn.in_transaction
    if outer:
        conn.execute("BEGIN IMMEDIATE")
    else:
        conn.execute("SAVEPOINT post_transfer")
    try:
        existing = conn.execute(
            "SELECT source,target,currency,amount_minor FROM transfers WHERE transfer_id=?",
            (transfer_id,),
        ).fetchone()
        if existing is not None:
            if tuple(existing) != (source, target, currency, minor):
                raise ValueError("transfer_id reused with conflicting fields")
            result = {"transfer_id": transfer_id, "amount_minor": existing[3], "entry_count": 2}
        else:
            for acct in (source, target):
                row = conn.execute(
                    "SELECT currency FROM accounts WHERE account_id=?", (acct,)
                ).fetchone()
                if row is None:
                    raise ValueError(f"account {acct!r} does not exist")
                if row[0] != currency:
                    raise ValueError(f"account {acct!r} currency mismatch")
            conn.execute(
                "INSERT INTO transfers(transfer_id,source,target,currency,amount_minor) VALUES(?,?,?,?,?)",
                (transfer_id, source, target, currency, minor),
            )
            conn.execute(
                "INSERT INTO entries(transfer_id,account_id,side,amount_minor,currency) VALUES(?,?,?,?,?)",
                (transfer_id, source, "debit", minor, currency),
            )
            conn.execute(
                "INSERT INTO entries(transfer_id,account_id,side,amount_minor,currency) VALUES(?,?,?,?,?)",
                (transfer_id, target, "credit", minor, currency),
            )
            result = {"transfer_id": transfer_id, "amount_minor": minor, "entry_count": 2}
    except BaseException:
        try:
            if outer:
                conn.rollback()
            else:
                conn.execute("ROLLBACK TO post_transfer")
                conn.execute("RELEASE post_transfer")
        except sqlite3.Error:
            pass
        raise
    if outer:
        conn.commit()
    else:
        conn.execute("RELEASE post_transfer")
    return result
