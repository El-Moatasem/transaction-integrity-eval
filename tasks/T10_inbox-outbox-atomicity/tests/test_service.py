import sqlite3,threading,json,pytest
from service import setup,apply_event,get_pending,mark_published

def db(tmp_path):
    p=tmp_path/'events.db';c=sqlite3.connect(p,timeout=10);setup(c)
    c.execute('INSERT INTO accounts VALUES(?,?)',('a',100));c.commit();return p,c

def test_apply_replay_and_pending(tmp_path):
    _,c=db(tmp_path)
    r=apply_event(c,'e1','a',-40)
    assert r=={'event_id':'e1','account_id':'a','balance_after_cents':60}
    assert apply_event(c,'e1','a',-40)==r
    with pytest.raises(ValueError):apply_event(c,'e1','a',-20)
    assert c.execute('SELECT balance_cents FROM accounts').fetchone()[0]==60
    pending=get_pending(c)
    assert pending==[{'event_id':'e1','topic':'account.changed','payload':{'event_id':'e1','account_id':'a','delta_cents':-40,'balance_after_cents':60}}]
    mark_published(c,'e1');mark_published(c,'e1')
    assert get_pending(c)==[]
    with pytest.raises(ValueError):mark_published(c,'missing')

def test_failure_in_outbox_rolls_back_everything(tmp_path):
    _,c=db(tmp_path)
    c.execute("CREATE TRIGGER deny_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'injected failure'); END;");c.commit()
    with pytest.raises(sqlite3.DatabaseError):apply_event(c,'blocked','a',-30)
    assert c.execute('SELECT balance_cents FROM accounts').fetchone()[0]==100
    assert c.execute('SELECT COUNT(*) FROM inbox').fetchone()[0]==0
    assert c.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]==0

def test_invalid_event_rollback(tmp_path):
    _,c=db(tmp_path)
    for event_id,account,delta in [('', 'a',1),('x','a',True),('x','a',0),('x','a',-101),('x','none',5)]:
        with pytest.raises(ValueError):apply_event(c,event_id,account,delta)
    assert c.execute('SELECT balance_cents FROM accounts').fetchone()[0]==100
    assert c.execute('SELECT COUNT(*) FROM inbox').fetchone()[0]==0

def test_pending_sort_and_two_events(tmp_path):
    _,c=db(tmp_path);apply_event(c,'z','a',10);apply_event(c,'b','a',-5)
    assert [x['event_id'] for x in get_pending(c)]==['b','z']
    assert [x['payload']['balance_after_cents'] for x in get_pending(c)]==[105,110]

from race_probe import pair_on_file, permissible_error

def test_competing_debits_preserve_balance_inbox_and_outbox(tmp_path):
    path, seed = db(tmp_path)
    seed.close()
    outcomes = pair_on_file(
        path,
        lambda conn: apply_event(conn, 'eventA', 'a', -70),
        lambda conn: apply_event(conn, 'eventB', 'a', -70),
        lambda sql: 'from inbox' in sql and 'where event_id' in sql,
    )
    for result, err in outcomes:
        assert permissible_error(err), f'unexpected competing event error: {err!r}'
        if result is not None:
            assert result['balance_after_cents'] == 30
    with sqlite3.connect(path, timeout=5) as conn:
        inbox = conn.execute('SELECT event_id, delta_cents, balance_after_cents FROM inbox').fetchall()
        outbox = conn.execute('SELECT event_id, payload, published FROM outbox').fetchall()
        balance = conn.execute("SELECT balance_cents FROM accounts WHERE account_id='a'").fetchone()[0]
        assert balance in (30, 100), 'account balance overdrawn or corrupted'
        assert len(inbox) <= 1 and len(outbox) == len(inbox)
        if not inbox:
            apply_event(conn, 'eventA', 'a', -70)
            inbox = conn.execute('SELECT event_id, delta_cents, balance_after_cents FROM inbox').fetchall()
            outbox = conn.execute('SELECT event_id, payload, published FROM outbox').fetchall()
            balance = conn.execute("SELECT balance_cents FROM accounts WHERE account_id='a'").fetchone()[0]
        assert balance == 30 and len(inbox) == len(outbox) == 1
        assert inbox[0][1:] == (-70, 30) and inbox[0][0] == outbox[0][0]
        assert outbox[0][2] == 0
        assert json.loads(outbox[0][1])['balance_after_cents'] == 30
        assert apply_event(conn, inbox[0][0], 'a', -70)['balance_after_cents'] == 30
        assert conn.execute('SELECT COUNT(*) FROM outbox').fetchone()[0] == 1
