import re

_CURRENCIES = {"USD", "EUR"}
_AMOUNT_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));""")
    conn.commit()


def _parse_amount_minor(amount):
    """Convert a decimal string with at most two significant fractional digits
    into integer minor units (cents). Never uses floats."""
    if not isinstance(amount, str) or not _AMOUNT_RE.fullmatch(amount):
        raise ValueError("amount must be a plain decimal string")
    whole, _, frac = amount.partition(".")
    if len(frac.rstrip("0")) > 2:
        raise ValueError("amount has more than two fractional digits")
    minor = int(whole) * 100 + int((frac + "00")[:2])
    if minor <= 0:
        raise ValueError("amount must be greater than zero")
    return minor


def _require_str(name, value):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def post_transfer(conn, transfer_id, source, target, amount, currency):
    # 1. Validate all inputs before touching the database.
    _require_str("transfer_id", transfer_id)
    _require_str("source", source)
    _require_str("target", target)
    _require_str("currency", currency)
    if currency not in _CURRENCIES:
        raise ValueError("unsupported currency")
    minor = _parse_amount_minor(amount)
    if source == target:
        raise ValueError("source and target must differ")

    try:
        # 2. Idempotency / conflict check against an existing transfer.
        existing = conn.execute(
            "SELECT source, target, currency, amount_minor FROM transfers WHERE transfer_id=?",
            (transfer_id,),
        ).fetchone()
        if existing is not None:
            if tuple(existing) != (source, target, currency, minor):
                raise ValueError("transfer_id already used with different fields")
            return {"transfer_id": transfer_id, "amount_minor": existing[3], "entry_count": 2}

        # 3. Both accounts must exist with the supplied currency.
        for account_id in (source, target):
            row = conn.execute(
                "SELECT currency FROM accounts WHERE account_id=?", (account_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"account {account_id!r} does not exist")
            if row[0] != currency:
                raise ValueError(f"account {account_id!r} currency mismatch")

        # 4. Atomic inserts: one transfer plus exactly two postings.
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
        conn.commit()
    except ValueError:
        # Validation failures happen before writes; roll back anyway to be safe.
        conn.rollback()
        raise
    except BaseException:
        # SQLite errors (constraints, triggers, ...) roll back and propagate unchanged.
        conn.rollback()
        raise

    return {"transfer_id": transfer_id, "amount_minor": minor, "entry_count": 2}
