import re

SUPPORTED_CURRENCIES = frozenset({"USD", "EUR"})
MINOR_UNITS = 2

# Plain decimal literal: "1", "1.2", "1.20", ".5". No sign, no exponent, no underscores.
_DECIMAL_RE = re.compile(r"^(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$")


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));""")
    conn.commit()


def _parse_amount_minor(amount):
    """Convert a decimal string to integer minor units without floats."""
    if not isinstance(amount, str) or not _DECIMAL_RE.fullmatch(amount):
        raise ValueError("amount must be a plain decimal string")
    whole, _, frac = amount.partition(".")
    frac = frac.rstrip("0")  # trailing zeros do not change the value
    if len(frac) > MINOR_UNITS:
        raise ValueError("amount has more than two significant fractional digits")
    minor = int(whole or "0") * 10 ** MINOR_UNITS + int(frac.ljust(MINOR_UNITS, "0") or "0")
    if minor <= 0:
        raise ValueError("amount must be greater than zero")
    return minor


def _validate_text(name, value):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def post_transfer(conn, transfer_id, source, target, amount, currency):
    # All validation happens before any write, so invalid calls leave the DB untouched.
    _validate_text("transfer_id", transfer_id)
    _validate_text("source", source)
    _validate_text("target", target)
    _validate_text("currency", currency)
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError("unsupported currency")
    minor = _parse_amount_minor(amount)
    if source == target:
        raise ValueError("source and target must differ")

    existing = conn.execute(
        "SELECT source, target, currency, amount_minor FROM transfers WHERE transfer_id=?",
        (transfer_id,),
    ).fetchone()
    if existing is not None:
        if tuple(existing) != (source, target, currency, minor):
            raise ValueError("transfer_id already used with different fields")
        return {"transfer_id": transfer_id, "amount_minor": minor, "entry_count": 2}

    for account_id in (source, target):
        row = conn.execute(
            "SELECT currency FROM accounts WHERE account_id=?", (account_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown account: {account_id}")
        if row[0] != currency:
            raise ValueError(f"account {account_id} does not hold {currency}")

    # Savepoint keeps the three writes atomic and leaves any caller transaction intact
    # on failure. Unexpected sqlite3 errors roll back and propagate unchanged.
    conn.execute("SAVEPOINT post_transfer")
    try:
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
        conn.execute("RELEASE post_transfer")
    except BaseException:
        conn.execute("ROLLBACK TO post_transfer")
        conn.execute("RELEASE post_transfer")
        raise
    conn.commit()
    return {"transfer_id": transfer_id, "amount_minor": minor, "entry_count": 2}
