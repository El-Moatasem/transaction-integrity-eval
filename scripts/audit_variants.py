#!/usr/bin/env python3
"""Check behavioral grader fairness with known-good and known-bad variants.

These are local evidence controls, not a guarantee against all false results.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from run_eval import select,grade_code


def check(tid,code,expected,label):
    result=grade_code(select(tid),code,timeout=55)
    ok=result['exit_code']==(0 if expected else 1)
    print(f"{tid}: {label}: {'PASS' if ok else 'FAIL'} "
          f"(grader={'pass' if result['passed'] else 'reject'})",flush=True)
    if not ok:print(result['log'][-1600:])
    return ok


def mutation(tid,old,new,expected,label):
    source=(select(tid)/'solution/service.py').read_text()
    if old not in source:
        print(f'{tid}: mutation anchor not found for {label}')
        return False
    with TemporaryDirectory(prefix='txn-variant-') as d:
        altered=Path(d)/'service.py'
        altered.write_text(source.replace(old,new,1))
        return check(tid,altered,expected,label)


def main():
    good=check('T02', ROOT/'audit_variants/T02_atomic_conditional_update.py',
               True,'independent atomic conditional-update approach accepted')

    # A deferred BEGIN is not inherently incorrect. A SQLite lock timeout is
    # permitted by these contracts when changes roll back and a retry is safe.
    for tid in ('T01','T02','T10'):
        good &= mutation(tid,"conn.execute('BEGIN IMMEDIATE')", "conn.execute('BEGIN')",
                         True,'valid deferred transaction accepted')

    # Deleting the transaction entirely (not merely changing BEGIN mode) is a
    # deliberate bug in the two read-before-write reference algorithms.
    for tid in ('T01','T02'):
        good &= mutation(tid,"conn.execute('BEGIN IMMEDIATE')",
                         "# intentionally deleted transaction start",
                         False,'unsafe read-before-write fix rejected')

    # Commit transfer before the second posting; second-entry failure leaves
    # a partial journal. It must be rejected by T03.
    good &= mutation('T03',
        "conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,target,'credit',minor,currency))",
        "conn.commit()\n            conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,target,'credit',minor,currency))",
        False,'partially committed journal rejected')

    # Commit balance + inbox before writing the durable outbox event. A trigger
    # blocking outbox insertion must then expose the partial state.
    good &= mutation('T10',
        "conn.execute('INSERT INTO outbox VALUES(?,?,?,0)',(event_id,'account.changed',payload))",
        "conn.commit()\n            conn.execute('INSERT INTO outbox VALUES(?,?,?,0)',(event_id,'account.changed',payload))",
        False,'balance/inbox committed without outbox rejected')
    return 0 if good else 1


if __name__=='__main__':
    sys.exit(main())
