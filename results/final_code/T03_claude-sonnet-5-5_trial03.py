import re

_AMOUNT_RE = re.compile(r'[0-9]+(?:\.[0-9]+)?')


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));""")
    conn.commit()


def _parse_minor(amount):
    if not isinstance(amount, str) or not _AMOUNT_RE.fullmatch(amount):
        raise ValueError('invalid amount')
    whole, _, frac = amount.partition('.')
    if frac[2:].strip('0'):
        raise ValueError('too many fractional digits')
    frac = (frac[:2] + '00')[:2]
    minor = int(whole) * 100 + int(frac)
    if minor <= 0 or minor > 2**63 - 1:
        raise ValueError('amount out of range')
    return minor


def post_transfer(conn, transfer_id, source, target, amount, currency):
    if not all(isinstance(x, str) for x in (transfer_id, source, target, currency)):
        raise ValueError('invalid argument')
    if currency not in ('USD', 'EUR'):
        raise ValueError('unsupported currency')
    minor = _parse_minor(amount)
    if source == target:
        raise ValueError('source equals target')

    started = False
    if not conn.in_transaction:
        conn.execute('BEGIN IMMEDIATE')
        started = True
    try:
        existing = conn.execute(
            'SELECT source,target,currency,amount_minor FROM transfers WHERE transfer_id=?',
            (transfer_id,)).fetchone()
        if existing:
            if tuple(existing) == (source, target, currency, minor):
                if started:
                    conn.rollback()
                return {'transfer_id': transfer_id, 'amount_minor': minor, 'entry_count': 2}
            raise ValueError('conflicting transfer id reuse')
        for acct in (source, target):
            row = conn.execute('SELECT currency FROM accounts WHERE account_id=?', (acct,)).fetchone()
            if row is None or row[0] != currency:
                raise ValueError('unknown account or currency mismatch')
        conn.execute('INSERT INTO transfers(transfer_id,source,target,currency,amount_minor) VALUES(?,?,?,?,?)',
                     (transfer_id, source, target, currency, minor))
        conn.execute('INSERT INTO entries(transfer_id,account_id,side,amount_minor,currency) VALUES(?,?,?,?,?)',
                     (transfer_id, source, 'debit', minor, currency))
        conn.execute('INSERT INTO entries(transfer_id,account_id,side,amount_minor,currency) VALUES(?,?,?,?,?)',
                     (transfer_id, target, 'credit', minor, currency))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return {'transfer_id': transfer_id, 'amount_minor': minor, 'entry_count': 2}
