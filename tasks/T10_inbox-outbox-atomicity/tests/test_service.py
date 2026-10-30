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
