import json

def setup(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,balance_cents INTEGER);
    CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,account_id TEXT,delta_cents INTEGER,balance_after_cents INTEGER);
    CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,topic TEXT,payload TEXT,published INTEGER);""");conn.commit()

def apply_event(conn,event_id,account_id,delta_cents):
    conn.execute('UPDATE accounts SET balance_cents=balance_cents+? WHERE account_id=?',(delta_cents,account_id));conn.commit()
    balance=conn.execute('SELECT balance_cents FROM accounts WHERE account_id=?',(account_id,)).fetchone()[0]
    conn.execute('INSERT INTO inbox VALUES(?,?,?,?)',(event_id,account_id,delta_cents,balance));conn.commit()
    payload=json.dumps({'event_id':event_id,'account_id':account_id,'delta_cents':delta_cents,'balance_after_cents':balance})
    conn.execute('INSERT INTO outbox VALUES(?,?,?,0)',(event_id,'account.changed',payload));conn.commit()
    return {'event_id':event_id,'account_id':account_id,'balance_after_cents':balance}

def get_pending(conn):
    return []

def mark_published(conn,event_id):
    conn.execute('UPDATE outbox SET published=1 WHERE event_id=?',(event_id,));conn.commit()
