import re

_CURRENCIES = frozenset({"USD", "EUR"})
_AMOUNT_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_MAX_MINOR = 2**63 - 1  # SQLite INTEGER limit


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));""")
    conn.commit()


def _parse_amount_minor(amount):
    """Parse a positive decimal string with at most two significant fractional digits
    into an integer count of minor units (cents). Never uses floats."""
    if not isinstance(amount, str) or not _AMOUNT_RE.fullmatch(amount):
        raise ValueError("amount must be a positive decimal string")
    whole, _, frac = amount.partition(".")
    frac = frac.rstrip("0")  # trailing zeros do not change the value
    if len(frac) > 2:
        raise ValueError("amount has more than two fractional digits")
    minor = int(whole) * 100 + int((frac + "00")[:2])
    if minor <= 0:
        raise ValueError("amount must be greater than zero")
    if minor > _MAX_MINOR:
        raise ValueError("amount is too large")
    return minor


def _validate_text(value, name):
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{name} must be a non-empty string")


def post_transfer(conn, transfer_id, source, target, amount, currency):
    # Pure input validation: nothing has been written yet, so failures leave the DB untouched.
    _validate_text(transfer_id, "transfer_id")
    _validate_text(source, "source")
    _validate_text(target, "target")
    _validate_text(currency, "currency")
    if currency not in _CURRENCIES:
        raise ValueError("unsupported currency")
    if source == target:
        raise ValueError("source and target must differ")
    minor = _parse_amount_minor(amount)

    # Everything below is one atomic unit. A SAVEPOINT starts a transaction when none is
    # open and nests inside the caller's transaction otherwise. On any exception we roll
    # back to the savepoint and re-raise unchanged (ValueError or sqlite3 errors alike).
    outermost = not conn.in_transaction
    conn.execute("SAVEPOINT post_transfer")
    try:
        existing = conn.execute(
            "SELECT source, target, currency, amount_minor FROM transfers WHERE transfer_id=?",
            (transfer_id,),
        ).fetchone()
        if existing is not None:
            if existing != (source, target, currency, minor):
                raise ValueError("transfer_id already used with different fields")
            result = {"transfer_id": transfer_id, "amount_minor": existing[3], "entry_count": 2}
        else:
            rows = conn.execute(
                "SELECT account_id, currency FROM accounts WHERE account_id IN (?, ?)",
                (source, target),
            ).fetchall()
            accounts = dict(rows)
            if accounts.get(source) != currency or accounts.get(target) != currency:
                raise ValueError("both accounts must exist and have the transfer currency")

            conn.execute(
                "INSERT INTO transfers(transfer_id, source, target, currency, amount_minor) VALUES(?,?,?,?,?)",
                (transfer_id, source, target, currency, minor),
            )
            conn.execute(
                "INSERT INTO entries(transfer_id, account_id, side, amount_minor, currency) VALUES(?,?,?,?,?)",
                (transfer_id, source, "debit", minor, currency),
            )
            conn.execute(
                "INSERT INTO entries(transfer_id, account_id, side, amount_minor, currency) VALUES(?,?,?,?,?)",
                (transfer_id, target, "credit", minor, currency),
            )
            result = {"transfer_id": transfer_id, "amount_minor": minor, "entry_count": 2}
    except BaseException:
        conn.execute("ROLLBACK TO post_transfer")
        conn.execute("RELEASE post_transfer")
        raise

    conn.execute("RELEASE post_transfer")
    if outermost:
        conn.commit()
    return result
