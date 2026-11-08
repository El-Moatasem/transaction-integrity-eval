import re
import sqlite3

SUPPORTED_CURRENCIES = {"USD": 2, "EUR": 2}
_AMOUNT_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def setup(conn):
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));"""
    )
    conn.commit()


def _parse_amount_minor(amount, exponent):
    """Parse a decimal string into integer minor units without floats."""
    if not isinstance(amount, str) or not _AMOUNT_RE.fullmatch(amount):
        raise ValueError("amount must be a positive decimal string")
    whole, _, frac = amount.partition(".")
    frac = frac.rstrip("0")
    if len(frac) > exponent:
        raise ValueError("amount has too many fractional digits")
    frac = frac.ljust(exponent, "0")
    minor = int(whole) * (10 ** exponent) + (int(frac) if frac else 0)
    if minor <= 0:
        raise ValueError("amount must be greater than zero")
    return minor


def _require_text(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def post_transfer(conn, transfer_id, source, target, amount, currency):
    _require_text(transfer_id, "transfer_id")
    _require_text(source, "source")
    _require_text(target, "target")
    if not isinstance(currency, str) or currency not in SUPPORTED_CURRENCIES:
        raise ValueError("unsupported currency")
    minor = _parse_amount_minor(amount, SUPPORTED_CURRENCIES[currency])
    if source == target:
        raise ValueError("source and target must differ")

    was_in_tx = conn.in_transaction
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
            conn.execute("ROLLBACK TO post_transfer")
            conn.execute("RELEASE post_transfer")
        finally:
            if not was_in_tx and conn.in_transaction:
                conn.rollback()
        raise
    conn.execute("RELEASE post_transfer")
    if conn.in_transaction:
        conn.commit()
    return result
