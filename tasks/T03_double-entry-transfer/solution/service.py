from decimal import Decimal,InvalidOperation

def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,currency TEXT);
    CREATE TABLE IF NOT EXISTS transfers(transfer_id TEXT PRIMARY KEY,source TEXT,target TEXT,currency TEXT,amount_minor INTEGER);
    CREATE TABLE IF NOT EXISTS entries(transfer_id TEXT,account_id TEXT,side TEXT,amount_minor INTEGER,currency TEXT,PRIMARY KEY(transfer_id,side));""");conn.commit()

def post_transfer(conn,transfer_id,source,target,amount,currency):
    if any(not isinstance(v,str) or not v for v in (transfer_id,source,target,amount)) or source==target or currency not in ('USD','EUR'):
        raise ValueError('invalid transfer')
    try:d=Decimal(amount)
    except (InvalidOperation,ValueError):raise ValueError('invalid amount')
    if not d.is_finite() or d<=0 or d*100!=(d*100).to_integral_value():raise ValueError('fractional cents')
    minor=int(d*100)
    try:
        conn.execute('BEGIN IMMEDIATE')
        old=conn.execute('SELECT source,target,currency,amount_minor FROM transfers WHERE transfer_id=?',(transfer_id,)).fetchone()
        if old:
            if old!=(source,target,currency,minor):raise ValueError('idempotency conflict')
        else:
            currencies=conn.execute('SELECT account_id,currency FROM accounts WHERE account_id IN (?,?)',(source,target)).fetchall()
            if len(currencies)!=2 or any(cur!=currency for _,cur in currencies):raise ValueError('currency mismatch')
            conn.execute('INSERT INTO transfers VALUES(?,?,?,?,?)',(transfer_id,source,target,currency,minor))
            conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,source,'debit',minor,currency))
            conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,target,'credit',minor,currency))
        conn.commit()
        return {'transfer_id':transfer_id,'amount_minor':minor,'entry_count':2}
    except BaseException:
        conn.rollback();raise
