import json
def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""");conn.commit()
def apply_event(conn,event_id,account_id,delta_cents):
    if not event_id or type(delta_cents) is not int or delta_cents==0:raise ValueError()
    try:
        conn.execute('BEGIN IMMEDIATE')
        old=conn.execute('SELECT account_id,delta_cents,balance_after_cents FROM inbox WHERE event_id=?',(event_id,)).fetchone()
        if old:
            if old[0]!=account_id or old[1]!=delta_cents:raise ValueError()
            result={'event_id':event_id,'account_id':account_id,'balance_after_cents':old[2]}
        else:
            old_balance=conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?',(account_id,)).fetchone()
            if not old_balance or old_balance[0]+delta_cents<0:raise ValueError()
            balance=old_balance[0]+delta_cents
            conn.execute('UPDATE accounts SET balance_cents=? WHERE account_id=?',(balance,account_id))
            conn.execute('INSERT INTO inbox VALUES(?,?,?,?)',(event_id,account_id,delta_cents,balance))
            # WRONG: outbox publishes previous rather than committed balance.
            payload=json.dumps({'event_id':event_id,'account_id':account_id,'delta_cents':delta_cents,'balance_after_cents':old_balance[0]},sort_keys=True,separators=(',',':'))
            conn.execute('INSERT INTO outbox VALUES(?,?,?,0)',(event_id,'account.changed',payload))
            result={'event_id':event_id,'account_id':account_id,'balance_after_cents':balance}
        conn.commit();return result
    except BaseException:
        conn.rollback();raise

def get_pending(conn):
    rows=conn.execute('SELECT event_id,topic,payload FROM outbox WHERE published=0 ORDER BY event_id').fetchall()
    return [{'event_id':id,'topic':topic,'payload':json.loads(payload)} for id,topic,payload in rows]
def mark_published(conn,event_id):
    if conn.execute('UPDATE outbox SET published=1 WHERE event_id=?',(event_id,)).rowcount!=1:
        conn.rollback();raise ValueError()
    conn.commit()
