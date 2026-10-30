import sqlite3,pytest
from service import setup,post_transfer

def db():
    c=sqlite3.connect(':memory:');setup(c)
    c.executemany('INSERT INTO accounts VALUES(?,?)',[('a','USD'),('b','USD'),('c','EUR')]);c.commit();return c

def test_balanced_exact_postings_and_replay():
    c=db();x=post_transfer(c,'t1','a','b','0.29','USD')
    assert x=={'transfer_id':'t1','amount_minor':29,'entry_count':2}
    assert post_transfer(c,'t1','a','b','0.2900','USD')==x
    entries=c.execute('SELECT account_id,side,amount_minor FROM entries ORDER BY side').fetchall()
    assert entries==[('b','credit',29),('a','debit',29)]
    assert c.execute('SELECT COUNT(*) FROM transfers').fetchone()[0]==1

def test_amount_and_currency_rules():
    c=db()
    for kwargs in [dict(amount='0'),dict(amount='0.001'),dict(amount='1.201'),dict(amount='NaN'),dict(amount='Inf'),dict(source='a',target='c'),dict(source='a',target='a'),dict(source='missing'),dict(currency='JPY'),dict(amount=0.29)]:
        args=dict(transfer_id='bad',source='a',target='b',amount='1.00',currency='USD');args.update(kwargs)
        with pytest.raises(ValueError):post_transfer(c,**args)
    assert c.execute('SELECT COUNT(*) FROM entries').fetchone()[0]==0

def test_conflicting_replay_does_not_modify_journal():
    c=db();post_transfer(c,'unique','a','b','2.00','USD')
    for k in [dict(amount='3.00'),dict(source='b',target='a')]:
        args=dict(transfer_id='unique',source='a',target='b',amount='2.00',currency='USD');args.update(k)
        with pytest.raises(ValueError):post_transfer(c,**args)
    assert c.execute('SELECT COUNT(*) FROM entries').fetchone()[0]==2

def test_extra_zeroes_allowed():
    c=db();assert post_transfer(c,'decimal','a','b','1.200','USD')['amount_minor']==120
