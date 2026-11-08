import re

_AMOUNT_RE = re.compile(r'([0-9]+)(?:\.([0-9]+))?')
_CURRENCIES = ('USD', 'EUR')


def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));""")
    conn.commit()


def _parse_minor(amount):
    if not isinstance(amount, str):
        raise ValueError('amount must be a string')
    m = _AMOUNT_RE.fullmatch(amount)
    if not m:
        raise ValueError('invalid amount')
    whole, frac = m.group(1), m.group(2) or ''
    if frac[2:].strip('0'):
        raise ValueError('too many fractional digits')
    minor = int(whole) * 100 + int((frac[:2] + '00')[:2])
    if minor <= 0:
        raise ValueError('amount must be positive')
    if minor > 2**63 - 1:
        raise ValueError('amount too large')
    return minor


def post_transfer(conn, transfer_id, source, target, amount, currency):
    for v in (transfer_id, source, target, currency):
        if not isinstance(v, str):
            raise ValueError('invalid argument')
    minor = _parse_minor(amount)
    if currency not in _CURRENCIES:
        raise ValueError('unsupported currency')
    if source == target:
        raise ValueError('source and target must differ')

    owns_tx = not conn.in_transaction
    if owns_tx:
        conn.execute('BEGIN IMMEDIATE')
    try:
        existing = conn.execute(
            'SELECT source,target,currency,amount_minor FROM transfers WHERE transfer_id=?',
            (transfer_id,)).fetchone()
        if existing is not None:
            if tuple(existing) != (source, target, currency, minor):
                raise ValueError('conflicting transfer id reuse')
            result = {'transfer_id': transfer_id, 'amount_minor': minor, 'entry_count': 2}
        else:
            for acct in (source, target):
                row = conn.execute('SELECT currency FROM accounts WHERE account_id=?',
                                   (acct,)).fetchone()
                if row is None:
                    raise ValueError('unknown account')
                if row[0] != currency:
                    raise ValueError('currency mismatch')
            conn.execute('INSERT INTO transfers(transfer_id,source,target,currency,amount_minor) VALUES(?,?,?,?,?)',
                         (transfer_id, source, target, currency, minor))
            conn.execute('INSERT INTO entries(transfer_id,account_id,side,amount_minor,currency) VALUES(?,?,?,?,?)',
                         (transfer_id, source, 'debit', minor, currency))
            conn.execute('INSERT INTO entries(transfer_id,account_id,side,amount_minor,currency) VALUES(?,?,?,?,?)',
                         (transfer_id, target, 'credit', minor, currency))
            result = {'transfer_id': transfer_id, 'amount_minor': minor, 'entry_count': 2}
        if owns_tx:
            conn.commit()
        return result
    except BaseException:
        if owns_tx:
            conn.rollback()
        raise
